from pathlib import Path
import re
from typing import TypedDict

from keef.music import read_audio
from keef.models import MusicTrack

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".ape",
    ".flac",
    ".m4a",
    ".mka",
    ".mp3",
    ".mp4",
    ".oga",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
    ".wv",
}

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_COLLAPSE_SPACE = re.compile(r"\s+")


class RenameEntry(TypedDict):
    source: str
    destination: str | None
    reason: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def sanitize_name(name: str) -> str:
    """
    sanitize_name: remove caracteres inválidos do filesystem e normaliza.

    input:
        name, nome bruto extraído dos metadados.

    output:
        str, nome limpo sem caracteres proibidos e sem espaços repetidos.
    """
    cleaned = _INVALID_CHARS.sub("", name)
    cleaned = _COLLAPSE_SPACE.sub(" ", cleaned).strip().rstrip(". ")

    return cleaned


def build_target_stem(track: MusicTrack) -> str | None:
    """
    build_target_stem: monta o novo nome do arquivo no formato padrão.

    input:
        track, metadados do arquivo baixado.

    output:
        str | None, stem sanitizado ou None quando não há título.
    """
    if not track.title:
        return None

    title = track.title.strip()
    artist = track.artist.strip() if track.artist else None

    if track.track_number is not None:
        stem = f"{track.track_number:02d}. {title}"

        if artist:
            stem = f"{stem} - {artist}"
    else:
        stem = title

        if artist:
            stem = f"{title} - {artist}"

    return sanitize_name(stem)


def unique_destination(directory: Path, stem: str, suffix: str, used: set[str]) -> Path:
    """
    unique_destination: resolve colisões de nome com sufixo numérico.

    input:
        directory, diretório de destino.
        stem, novo nome sem extensão.
        suffix, extensão original do arquivo.
        used, nomes já reservados no diretório.

    output:
        Path, caminho final sem colisão.
    """
    candidate = f"{stem}{suffix}"

    if candidate not in used:
        used.add(candidate)
        return directory / candidate

    index = 1

    while f"{stem} ({index}){suffix}" in used:
        index += 1

    candidate = f"{stem} ({index}){suffix}"
    used.add(candidate)

    return directory / candidate


def plan_renames(directory: Path) -> list[RenameEntry]:
    """
    plan_renames: calcula renomeações para arquivos de áudio de um diretório.

    input:
        directory, diretório com os arquivos baixados.

    output:
        list[RenameEntry], entradas com origem, destino e motivo.
    """
    entries: list[RenameEntry] = []
    used: set[str] = {path.name for path in directory.iterdir() if path.is_file()}

    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
            continue

        try:
            track = read_audio(path)
        except Exception as error:
            entries.append(
                {
                    "source": str(path),
                    "destination": None,
                    "reason": f"não foi possível ler: {error}",
                }
            )
            continue

        stem = build_target_stem(track)

        if stem is None:
            entries.append(
                {
                    "source": str(path),
                    "destination": None,
                    "reason": "sem título nos metadados",
                }
            )
            continue

        if (directory / f"{stem}{path.suffix}") == path:
            entries.append(
                {
                    "source": str(path),
                    "destination": str(path),
                    "reason": "já está no formato",
                }
            )
            continue

        destination = unique_destination(directory, stem, path.suffix, used)
        entries.append(
            {
                "source": str(path),
                "destination": str(destination),
                "reason": "renomear",
            }
        )

    return entries

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━