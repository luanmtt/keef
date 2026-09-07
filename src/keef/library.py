from pathlib import Path

from pydantic import BaseModel, Field

from keef.music import try_read_audio
from keef.models import MusicTrack

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class LibraryScanResult(BaseModel):
    tracks: list[MusicTrack] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)


def scan_library(root: Path) -> LibraryScanResult:
    """
    scan_library: percorre diretório e lê áudios recursivamente.

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
        if not path.is_file():
            continue

        result = try_read_audio(path)
        relative_path = path.relative_to(root)

        if isinstance(result, str):
            errors.append({"path": str(relative_path), "error": result})
            continue

        tracks.append(result.model_copy(update={"path": str(relative_path)}))

    return LibraryScanResult(tracks=tracks, errors=errors)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
