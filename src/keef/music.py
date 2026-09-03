from pathlib import Path
from collections.abc import Mapping
import re
from typing import TypedDict

from mutagen import MutagenError
from mutagen.mp3 import MP3

from keef.models import MusicTrack

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class FilenameMetadata(TypedDict, total=False):
    track_number: int
    artist: str
    title: str


def _first_tag(tags: object, key: str) -> str | None:
    """
    _first_tag: extrai o primeiro valor de uma tag ID3.

    input:
        tags, coleção de tags retornada pelo Mutagen.
        key, nome da tag procurada.

    output:
        str | None, valor textual ou None quando ausente.
    """
    if not isinstance(tags, Mapping):
        return None

    value = tags.get(key)

    if value is None:
        return None

    if isinstance(value, (list, tuple)):
        return str(value[0]) if value else None

    return str(value)


def _track_number(value: str | None) -> int | None:
    """
    _track_number: converte uma tag de faixa em número inteiro.

    input:
        value, texto como "1" ou "1/12".

    output:
        int | None, número da faixa ou None quando inválido.
    """
    if not value:
        return None

    try:
        return int(value.split("/", maxsplit=1)[0])
    except ValueError:
        return None


def _filename_metadata(path: Path) -> FilenameMetadata:
    """
    _filename_metadata: extrai metadados básicos do nome do arquivo.

    input:
        path, caminho do arquivo MP3.

    output:
        FilenameMetadata, campos encontrados como fallback das tags.
    """
    match = re.match(
        r"^(?P<track>\d+)[.\s-]+(?P<artist>[^-]+?)\s+-\s+(?P<title>.+)$",
        path.stem,
    )

    if match is None:
        return {}

    return {
        "track_number": int(match.group("track")),
        "artist": match.group("artist").strip(),
        "title": match.group("title").strip(),
    }

def read_mp3(path: Path) -> MusicTrack:
    """
    read_mp3: lê tags e propriedades técnicas de um MP3.

    input:
        path, caminho do arquivo MP3.

    output:
        MusicTrack, metadados normalizados e diagnósticos de ausência.
    """
    audio = MP3(path)
    tags = audio.tags
    filename_values = _filename_metadata(path)
    title = _first_tag(tags, "TIT2") or filename_values.get("title")
    artist = _first_tag(tags, "TPE1") or filename_values.get("artist")
    album = _first_tag(tags, "TALB")
    track_number = _track_number(_first_tag(tags, "TRCK"))
    track_number = track_number or filename_values.get("track_number")
    missing_metadata = [
        name
        for name, value in {
            "title": title,
            "artist": artist,
            "album": album,
            "track_number": track_number,
        }.items()
        if value is None
    ]

    return MusicTrack(
        path=str(path),
        title=title,
        artist=artist,
        album=album,
        track_number=track_number,
        duration_seconds=audio.info.length,
        bitrate_kbps=round(audio.info.bitrate / 1000),
        missing_metadata=missing_metadata,
    )


def try_read_mp3(path: Path) -> MusicTrack | str:
    """
    try_read_mp3: lê MP3 e converte falhas em diagnóstico.

    input:
        path, caminho do arquivo MP3.

    output:
        MusicTrack ou str, metadados válidos ou mensagem de erro.
    """
    if not path.exists():
        return f"Arquivo não encontrado: {path}"

    try:
        return read_mp3(path)
    except FileNotFoundError:
        return f"Arquivo não encontrado: {path}"
    except (OSError, MutagenError) as error:
        return f"Não foi possível ler o MP3 {path}: {error}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
