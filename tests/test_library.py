from pathlib import Path

import pytest

import keef.library
from keef.models import MusicTrack

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_scan_library_recurses_and_keeps_errors(monkeypatch, tmp_path) -> None:
    """
    test_scan_library_recurses_and_keeps_errors: verifica scan recursivo.

    input:
        diretório com áudios válidos, inválidos e arquivos não-audio.

    output:
        None, teste aprovado quando sucessos e erros são separados.
    """
    valid_path = tmp_path / "album" / "valid.flac"
    invalid_path = tmp_path / "broken.mp3"
    ignored_path = tmp_path / "cover.jpg"
    valid_path.parent.mkdir()
    valid_path.touch()
    invalid_path.touch()
    ignored_path.touch()

    def fake_reader(path: Path) -> MusicTrack | str:
        """
        fake_reader: simula parser de arquivos.

        input:
            path, caminho recebido pelo scanner.

        output:
            MusicTrack ou str, sucesso para valid.flac e erro para os demais.
        """
        if path == valid_path:
            return MusicTrack(path=str(path), title="Blue", format="flac")

        return "áudio inválido"

    monkeypatch.setattr(keef.library, "try_read_audio", fake_reader)

    result = keef.library.scan_library(tmp_path)

    assert len(result.tracks) == 1
    assert result.tracks[0].title == "Blue"
    assert result.tracks[0].path == "album/valid.flac"
    assert result.errors == [
        {"path": "broken.mp3", "error": "áudio inválido"},
    ]


def test_scan_library_rejects_missing_directory(tmp_path) -> None:
    """
    test_scan_library_rejects_missing_directory: rejeita diretório ausente.

    input:
        caminho que não é diretório.

    output:
        None, teste aprovado quando NotADirectoryError ocorre.
    """
    with pytest.raises(NotADirectoryError):
        keef.library.scan_library(tmp_path / "missing")


def test_scan_library_detects_album_folders(monkeypatch, tmp_path) -> None:
    """
    test_scan_library_detects_album_folders: detecta pastas como álbuns.

    input:
        diretório com pasta de álbum contendo faixas.

    output:
        None, teste aprovado quando faixas da pasta são incluídas na lista de tracks.
    """
    album_dir = tmp_path / "Blonde"
    album_dir.mkdir()
    track1 = album_dir / "01 Nikes.flac"
    track2 = album_dir / "02 Ivy.flac"
    track1.touch()
    track2.touch()

    def fake_reader(path: Path) -> MusicTrack:
        """
        fake_reader: simula parser de áudio.

        input:
            path, caminho recebido pelo scanner.

        output:
            MusicTrack, metadados simulados.
        """
        return MusicTrack(
            path=str(path),
            title=path.stem.split(" ", 1)[-1],
            artist="Frank Ocean",
            album="Blonde",
            format="flac",
        )

    monkeypatch.setattr(keef.library, "try_read_audio", fake_reader)

    result = keef.library.scan_library(tmp_path)

    assert len(result.tracks) == 2
    assert result.tracks[0].path == "Blonde/01 Nikes.flac"
    assert result.tracks[0].artist == "Frank Ocean"
    assert result.tracks[1].path == "Blonde/02 Ivy.flac"


def test_scan_library_mixed_files_and_folders(monkeypatch, tmp_path) -> None:
    """
    test_scan_library_mixed_files_and_folders: mistura arquivos e pastas.

    input:
        diretório com arquivo individual e pasta de álbum.

    output:
        None, teste aprovado quando todas as tracks são incluídas.
    """
    individual = tmp_path / "standalone.flac"
    individual.touch()
    album_dir = tmp_path / "Album"
    album_dir.mkdir()
    album_track = album_dir / "01 Track.flac"
    album_track.touch()

    def fake_reader(path: Path) -> MusicTrack:
        """
        fake_reader: simula parser de áudio.

        input:
            path, caminho recebido pelo scanner.

        output:
            MusicTrack, metadados simulados.
        """
        return MusicTrack(path=str(path), title="T", format="flac")

    monkeypatch.setattr(keef.library, "try_read_audio", fake_reader)

    result = keef.library.scan_library(tmp_path)

    assert len(result.tracks) == 2
    paths = {t.path for t in result.tracks}
    assert "standalone.flac" in paths
    assert "Album/01 Track.flac" in paths


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
