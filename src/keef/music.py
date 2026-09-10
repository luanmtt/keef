from collections.abc import Mapping
from pathlib import Path
import re
from typing import TypedDict

from mutagen import File as MutagenFile
from mutagen import MutagenError

from keef.models import MusicTrack

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LOSSLESS_FORMATS = {"aiff", "ape", "flac", "wav", "wv"}


class FilenameMetadata(TypedDict, total=False):
    track_number: int
    artist: str
    title: str


def _first_tag(tags: object, *keys: str) -> str | None:
    """
    _first_tag: extrai o primeiro valor de tags comuns.

    input:
        tags, coleção de metadados retornada pelo Mutagen.
        keys, nomes alternativos da tag procurada.

    output:
        str | None, valor textual ou None quando ausente.
    """
    if tags is None:
        return None

    for key in keys:
        try:
            value = tags[key]
        except Exception:
            value = getattr(tags, "get", lambda *_: None)(key)

        if value is None:
            continue

        if isinstance(value, (list, tuple)):
            return str(value[0]) if value else None

        return str(value)

    return None


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
        path, caminho do arquivo de áudio.

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


def _quality_value(info: object, attribute: str) -> int | None:
    """
    _quality_value: lê uma propriedade técnica opcional do stream.

    input:
        info, objeto de informações do Mutagen.
        attribute, nome da propriedade técnica.

    output:
        int | None, valor técnico quando disponível.
    """
    value = getattr(info, attribute, None)

    if isinstance(value, (int, float)):
        return int(value)

    return None


def read_audio(path: Path) -> MusicTrack:
    """
    read_audio: detecta formato e lê metadados de um arquivo de áudio.

    input:
        path, caminho do arquivo de áudio.

    output:
        MusicTrack, metadados e qualidade normalizados.
    """
    audio = MutagenFile(path, easy=True)

    if audio is None:
        raise MutagenError("formato de áudio não reconhecido")

    tags = audio.tags
    info = audio.info
    filename_values = _filename_metadata(path)
    suffix = path.suffix.lower().removeprefix(".")
    detected_format = suffix or audio.__class__.__name__.lower()
    title = _first_tag(tags, "title", "TIT2") or filename_values.get("title")
    artist = _first_tag(tags, "artist", "TPE1") or filename_values.get("artist")
    album = _first_tag(tags, "album", "TALB")
    track_number = _track_number(_first_tag(tags, "tracknumber", "TRCK"))
    track_number = track_number or filename_values.get("track_number")
    bitrate = _quality_value(info, "bitrate")
    bitrate_kbps = round(bitrate / 1000) if bitrate is not None else None
    title = title.strip() if isinstance(title, str) else None
    artist = artist.strip() if isinstance(artist, str) else None
    album = album.strip() if isinstance(album, str) else None
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
        format=detected_format,
        codec=audio.__class__.__name__,
        title=title,
        artist=artist,
        album=album,
        track_number=track_number,
        duration_seconds=_quality_value(info, "length"),
        bitrate_kbps=bitrate_kbps,
        sample_rate_hz=_quality_value(info, "sample_rate"),
        channels=_quality_value(info, "channels"),
        lossless=True if detected_format in LOSSLESS_FORMATS else False,
        missing_metadata=missing_metadata,
    )


def read_mp3(path: Path) -> MusicTrack:
    """
    read_mp3: mantém compatibilidade com o parser anterior.

    input:
        path, caminho de um arquivo de áudio.

    output:
        MusicTrack, metadados detectados pelo parser genérico.
    """
    return read_audio(path)


def try_read_audio(path: Path) -> MusicTrack | str:
    """
    try_read_audio: lê áudio e converte falhas em diagnóstico.

    input:
        path, caminho do arquivo de áudio.

    output:
        MusicTrack ou str, metadados válidos ou mensagem de erro.
    """
    if not path.exists():
        return f"Arquivo não encontrado: {path}"

    try:
        return read_audio(path)
    except FileNotFoundError:
        return f"Arquivo não encontrado: {path}"
    except (OSError, MutagenError) as error:
        return f"Não foi possível ler o áudio {path}: {error}"


def try_read_mp3(path: Path) -> MusicTrack | str:
    """
    try_read_mp3: mantém compatibilidade com a API anterior.

    input:
        path, caminho do arquivo de áudio.

    output:
        MusicTrack ou str, resultado do parser genérico.
    """
    return try_read_audio(path)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
