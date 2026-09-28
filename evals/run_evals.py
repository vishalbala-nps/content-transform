"""Run every format over every fixture, score the results, report what moved.

    uv run --env-file .env python -m evals.run_evals
        [--formats linkedin,x_thread] [--fixtures press_release]
        [--config '{"audience": "executive", "detail_level": "brief"}'] [--no-cache] [-v]

Each run writes evals/runs/<timestamp>/: per fixture the brief and every
format's payload and artifacts, plus summary.json and report.md. Scores are
compared with the latest run over the same fixtures, formats and
GenerationConfig (defaults unless --config is given). The dev
cache stays on unless --no-cache is given, so after a format prompt change
only that format's calls hit the model.
"""

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from app.core.llm import LLMError
from app.core.usage import Usage, metered, total
from app.formats.base import GenerationConfig
from app.formats.brief_view import brief_for_prompt
from app.formats.registry import ADAPTERS
from app.formats.runner import FormatResult, run_formats
from app.ingest.text import ingest_text
from app.understand.brief import build_brief
from app.understand.schemas import ContentBrief
from app.verify.grounding import NUMBER, number_value

ROOT = Path(__file__).parent
FIXTURES = ROOT / "fixtures"
RUNS = ROOT / "runs"


def score_brief(brief: ContentBrief, exp: dict) -> dict:
    dumped = brief.model_dump_json().lower()
    missed = [s for s in exp["must_capture"] if s.lower() not in dumped]
    items = [*brief.claims, *brief.stats, *brief.timeline, *brief.actions]
    return {
        "captured": len(exp["must_capture"]) - len(missed),
        "must_capture": len(exp["must_capture"]),
        "missed": missed,
        "kind_ok": brief.source.kind == exp["source_kind"],
        "kind": brief.source.kind,
        "security_ok": (brief.security is not None) == exp["security"],
        "claims": len(brief.claims),
        "unsupported": sum(not i.support for i in items),
    }


def score_format(result: FormatResult, brief: ContentBrief, exp: dict) -> dict:
    if result.error:
        return {"error": result.error}
    text = "\n".join(a.text for a in result.artifacts if a.text is not None)
    # Numbers the model wrote that appear nowhere in the brief it was given.
    # Compared as grouping-free values, as the grounding check does: "20000" is "20,000".
    known = {number_value(n) for n in NUMBER.findall(brief_for_prompt(brief, public=False))}
    written = {n for n in NUMBER.findall(json.dumps(result.payload, ensure_ascii=False)) if number_value(n) not in known}
    grounding = result.grounding
    return {
        "warnings": result.warnings,
        "ioc_leaks": [i for i in exp["iocs"] if i in text] if ADAPTERS[result.name].public else [],
        "invented_numbers": sorted(written),
        # Passages the grounding check flagged, as "path: reasons".
        "passages": len(grounding.passages) if grounding else 0,
        "flagged": [f"{p.path}: {'; '.join(p.reasons)}" for p in grounding.passages if p.reasons]
        if grounding
        else [],
        "grounding_error": grounding.error if grounding else None,
    }


async def run_fixture(name: str, exp: dict, formats: list[str], config: GenerationConfig, out: Path) -> dict:
    source = ingest_text((FIXTURES / f"{name}.md").read_text())
    try:
        with metered() as brief_usage:
            brief = await build_brief(source)
    except LLMError as e:
        return {"brief": {"error": str(e)}, "formats": {}, "usage": brief_usage.model_dump()}
    out.mkdir(parents=True)
    (out / "brief.json").write_text(brief.model_dump_json(indent=2))

    scores = {}
    usage = total(brief_usage)
    for result in await run_formats(formats, brief, config):
        if result.usage:
            usage.add(total(result.usage.generate, result.usage.ground))
        fmt_dir = out / result.name
        fmt_dir.mkdir()
        if result.error:
            (fmt_dir / "error.txt").write_text(result.error)
        else:
            (fmt_dir / "payload.json").write_text(json.dumps(result.payload, indent=2, ensure_ascii=False))
        for artifact in result.artifacts:
            if artifact.data is not None:
                (fmt_dir / artifact.filename).write_bytes(artifact.data)
            else:
                (fmt_dir / artifact.filename).write_text(artifact.text or "")
        scores[result.name] = score_format(result, brief, exp)
    return {"brief": score_brief(brief, exp), "formats": scores, "usage": usage.model_dump()}


def delta(now: float, before: float | None, lower_is_better: bool = False) -> str:
    if before is None or now == before:
        return ""
    better = (now < before) if lower_is_better else (now > before)
    return f" ({now - before:+g}{' ✓' if better else ' ✗'})"


def totals(fixtures: dict) -> dict:
    briefs = [f["brief"] for f in fixtures.values() if "error" not in f["brief"]]
    outputs = [s for f in fixtures.values() for s in f["formats"].values()]
    ok = [s for s in outputs if "error" not in s]
    return {
        "facts captured": sum(b["captured"] for b in briefs),
        "kind correct": sum(b["kind_ok"] for b in briefs),
        "security correct": sum(b["security_ok"] for b in briefs),
        "unsupported items": sum(b["unsupported"] for b in briefs),
        "format warnings": sum(len(s["warnings"]) for s in ok),
        "IOC leaks": sum(len(s["ioc_leaks"]) for s in ok),
        "invented numbers": sum(len(s["invented_numbers"]) for s in ok),
        # .get: runs from before S7 have no grounding scores.
        "flagged passages": sum(len(s.get("flagged", [])) for s in ok),
        "passages": sum(s.get("passages", 0) for s in ok),
        "errors": len(fixtures) - len(briefs) + len(outputs) - len(ok),
    }


def _non_default(config: dict) -> dict:
    """The config fields that differ from GenerationConfig's defaults."""
    defaults = GenerationConfig().model_dump(mode="json")
    return {k: v for k, v in config.items() if v != defaults.get(k)}


def report(summary: dict, previous: dict | None) -> str:
    prev_totals = previous["totals"] if previous else {}
    lower_better = {
        "unsupported items", "format warnings", "IOC leaks", "invented numbers", "flagged passages", "errors"
    }  # fmt: skip
    lines = [f"# Eval run {summary['run']}", "", f"model {summary['model']}, cache {summary['cache']}", ""]
    if changed := _non_default(summary["config"]):
        lines += [f"config: {json.dumps(changed)}", ""]
    u = Usage.model_validate(summary["usage"])
    lines += [
        f"usage: {u.calls} model calls, {u.cached_calls} from cache, {u.input_tokens:,} input and "
        f"{u.output_tokens:,} output tokens, ${u.cost_usd:.4f}"
        + (f" plus {u.unpriced_calls} calls with no price" if u.unpriced_calls else ""),
        "",
    ]
    if previous:
        lines += [f"Compared with {previous['run']}.", ""]
    lines += ["| Total | Value |", "|---|---|"]
    for k, v in summary["totals"].items():
        lines.append(f"| {k} | {v}{delta(v, prev_totals.get(k), k in lower_better)} |")

    lines += ["", "## Briefs", "", "| Fixture | Facts | Kind | Security | Claims | Unsupported | Missed |",
              "|---|---|---|---|---|---|---|"]  # fmt: skip
    for name, f in summary["fixtures"].items():
        b = f["brief"]
        if "error" in b:
            lines.append(f"| {name} | error: {b['error']} ||||||")
            continue
        lines.append(
            f"| {name} | {b['captured']}/{b['must_capture']} | {'ok' if b['kind_ok'] else b['kind']} "
            f"| {'ok' if b['security_ok'] else 'wrong'} | {b['claims']} | {b['unsupported']} "
            f"| {', '.join(b['missed'])} |"
        )

    lines += ["", "## Formats", "",
              "| Fixture | Format | Warnings | IOC leaks | Invented numbers | Flagged passages |",
              "|---|---|---|---|---|---|"]  # fmt: skip
    for name, f in summary["fixtures"].items():
        for fmt, s in f["formats"].items():
            if "error" in s:
                lines.append(f"| {name} | {fmt} | error: {s['error']} ||||")
                continue
            flagged = "<br>".join(s["flagged"]) or f"0 of {s['passages']}"
            if s["grounding_error"]:
                flagged += f"<br>grounding error: {s['grounding_error']}"
            lines.append(
                f"| {name} | {fmt} | {'; '.join(s['warnings'])} | {', '.join(s['ioc_leaks'])} "
                f"| {', '.join(s['invented_numbers'])} | {flagged} |"
            )
    return "\n".join(lines) + "\n"


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--formats", help="comma-separated format names (default: all)")
    parser.add_argument("--fixtures", help="comma-separated fixture names (default: all)")
    parser.add_argument("--config", help="GenerationConfig fields as JSON (default: all defaults)")
    parser.add_argument("--no-cache", action="store_true", help="bypass the dev LLM cache")
    parser.add_argument("-v", "--verbose", action="store_true", help="log every model call")
    args = parser.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        logging.getLogger("app").setLevel(logging.INFO)
        logging.getLogger("google_genai._api_client").setLevel(logging.INFO)  # SDK retries
    if args.no_cache:
        os.environ["LLM_CACHE"] = "0"

    expectations = json.loads((FIXTURES / "expectations.json").read_text())
    formats = args.formats.split(",") if args.formats else list(ADAPTERS)
    fixtures = args.fixtures.split(",") if args.fixtures else list(expectations)
    unknown = [f for f in formats if f not in ADAPTERS] + [f for f in fixtures if f not in expectations]
    if unknown:
        parser.error(f"unknown format or fixture: {', '.join(unknown)}")
    try:
        config = GenerationConfig.model_validate_json(args.config or "{}")
    except ValueError as e:
        parser.error(f"invalid --config: {e}")
    config_json = config.model_dump(mode="json")

    # Totals are only comparable with a run by the same model over the same
    # fixtures and formats with the same config. Runs from before Ollama have
    # no provider (Gemini); runs from before S8 have no config (the defaults).
    # The first default-config run after prompts started reading the config
    # is compared with a pre-S8 run on purpose: that is what the change moved.
    settings = get_settings()
    previous = None
    for path in sorted(RUNS.glob("*/summary.json"), reverse=True):
        candidate = json.loads(path.read_text())
        same_model = (candidate.get("provider", "gemini"), candidate["model"]) == (
            settings.llm_provider,
            settings.llm_model,
        )
        same_config = _non_default(candidate.get("config", {})) == _non_default(config_json)
        if same_model and same_config and (candidate["formats"], list(candidate["fixtures"])) == (formats, fixtures):
            previous = candidate
            break

    run = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = RUNS / run
    results = await asyncio.gather(
        *(run_fixture(n, expectations[n], formats, config, out / n) for n in fixtures)
    )
    scored = dict(zip(fixtures, results))

    summary = {
        "run": run,
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "cache": "on" if settings.llm_cache else "off",
        "formats": formats,
        "config": config_json,
        "usage": total(*(Usage.model_validate(f["usage"]) for f in scored.values())).model_dump(),
        "fixtures": scored,
        "totals": totals(scored),
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    text = report(summary, previous)
    (out / "report.md").write_text(text)
    print(text)
    print(f"Written to {out.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    asyncio.run(main())
