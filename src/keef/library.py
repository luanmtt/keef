from pathlib import Path

from pydantic import BaseModel, Field

from keef.music import try_read_mp3
from keef.models import MusicTrack

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class LibraryScanResult(BaseModel):
    tracks: list[MusicTrack] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)


def scan_library(root: Path) -> LibraryScanResult:
    """
    scan_library: percorre diretório e lê MP3s recursivamente.

    input:
        root, diretório da biblioteca musical.

    output:
        LibraryScanResult, tracks válidas e erros individuais do parsing.
    """
    if not root.is_dir():
        raise NotADirectoryError(f"Diretório não encontrado: {root}")

    tracks = []
    errors = []

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".mp3":
            continue

        result = try_read_mp3(path)

        if isinstance(result, str):
            errors.append({"path": str(path), "error": result})
            continue

        tracks.append(result)

    return LibraryScanResult(tracks=tracks, errors=errors)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
