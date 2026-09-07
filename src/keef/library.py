from pathlib import Path

from pydantic import BaseModel, Field

from keef.music import try_read_audio
from keef.models import AlbumScan, MusicTrack

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class LibraryScanResult(BaseModel):
    tracks: list[MusicTrack] = Field(default_factory=list)
    albums: list[AlbumScan] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)


def _scan_album_folder(folder: Path) -> AlbumScan:
    """
    _scan_album_folder: lê faixas de uma pasta de álbum.

    input:
        folder, caminho da pasta do álbum.

    output:
        AlbumScan, faixas lidas e metadados do álbum.
    """
    tracks = []
    errors = []

    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue

        result = try_read_audio(path)

        if isinstance(result, str):
            errors.append({"path": path.name, "error": result})
            continue

        tracks.append(result.model_copy(update={"path": path.name}))

    artist = None
    album_name = None

    for track in tracks:
        if track.artist:
            artist = track.artist
            break

    for track in tracks:
        if track.album:
            album_name = track.album
            break

    return AlbumScan(
        folder_name=folder.name,
        artist=artist,
        album=album_name or folder.name,
        tracks=tracks,
        errors=errors,
        track_count=len(tracks),
    )


def scan_library(root: Path) -> LibraryScanResult:
    """
    scan_library: percorre diretório e lê áudios recursivamente.

    input:
        root, diretório da biblioteca musical.

    output:
        LibraryScanResult, tracks válidas, álbuns e erros individuais do parsing.
    """
    if not root.is_dir():
        raise NotADirectoryError(f"Diretório não encontrado: {root}")

    tracks = []
    albums = []
    errors = []

    for path in sorted(root.iterdir()):
        if path.is_dir():
            album = _scan_album_folder(path)
            albums.append(album)
            continue

        if not path.is_file():
            continue

        result = try_read_audio(path)
        relative_path = path.relative_to(root)

        if isinstance(result, str):
            errors.append({"path": str(relative_path), "error": result})
            continue

        tracks.append(result.model_copy(update={"path": str(relative_path)}))

    return LibraryScanResult(tracks=tracks, albums=albums, errors=errors)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
