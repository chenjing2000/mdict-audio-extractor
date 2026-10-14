from pathlib import Path
from tempfile import NamedTemporaryFile


def existing_audio(path: Path) -> Path | None:
    for suffix in (".mp3", ".wav"):
        candidate = path.with_suffix(suffix)
        if candidate.is_file():
            return candidate
    return None


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(payload)
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
