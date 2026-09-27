# Evals

Test data only. Nothing in `app/` reads from this folder.

`fixtures/` holds the source documents every eval run uses. They are
synthetic: every organisation, person, product and CVE id is invented, and IPs
and domains use reserved documentation ranges (`198.51.100.0/24`,
`203.0.113.0/24`, `.example`).

| Fixture | Exercises |
|---|---|
| `security_advisory` | CVEs, CVSS, affected versions, IOCs, actions, timeline |
| `incident_news` | informal tone, allegation vs. company denial, attribution, IOCs inside prose |
| `government_memo` | directives as actions, deadlines, non-security source |
| `research_report` | stats density, a markdown table, recommendations |
| `press_release` | marketing superlatives that must be attributed, not restated |

`fixtures/expectations.json` lists, for each fixture:

- `source_kind`, `security`: what the brief should classify the source as.
- `must_capture`: strings that should appear verbatim somewhere in the brief.
- `iocs`: strings that must never appear in a public-facing format.

To add a fixture, drop a `.md` file in `fixtures/` and add its entry to
`expectations.json`. Real public documents make better fixtures than invented
ones, so add them when you have them.
