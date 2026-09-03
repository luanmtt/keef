from pathlib import Path

import pytest

import keef.library
from keef.models import MusicTrack

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_scan_library_recurses_and_keeps_errors(monkeypatch, tmp_path) -> None:
    """
    test_scan_library_recurses_and_keeps_errors: verifica scan recursivo.

    input:
        diretório com MP3s válidos, inválidos e arquivos ignorados.

    output:
        None, teste aprovado quando sucessos e erros são separados.
    """
    valid_path = tmp_path / "album" / "valid.mp3"
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
            MusicTrack ou str, sucesso para valid.mp3 e erro para os demais.
        """
        if path == valid_path:
            return MusicTrack(path=str(path), title="Blue")

        return "MP3 inválido"

    monkeypatch.setattr(keef.library, "try_read_mp3", fake_reader)

    result = keef.library.scan_library(tmp_path)

    assert len(result.tracks) == 1
    assert result.tracks[0].title == "Blue"
    assert result.errors == [{"path": str(invalid_path), "error": "MP3 inválido"}]


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
