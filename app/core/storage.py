"""Binary artifacts (PDF, PPTX, PNG), stored by key under storage/artifacts/.

Keys are relative paths such as "<job id>/<format>/<filename>". Callers only
ever save and read by key, so moving to S3 means replacing these functions.
Text artifacts stay on the job row and never come here.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "storage" / "artifacts"


def _file(key: str) -> Path:
    path = (ROOT / key).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"storage key escapes the storage root: {key!r}")
    return path


def save(key: str, data: bytes) -> None:
    path = _file(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read(key: str) -> bytes:
    """Raises FileNotFoundError for a key that was never saved."""
    return _file(key).read_bytes()
