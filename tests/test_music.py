from pathlib import Path

import keef.music
from keef.models import MusicTrack

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class FakeInfo:
    length = 210.5
    bitrate = 320000


class FakeAudio:
    info = FakeInfo()
    tags = {
        "TIT2": ["Blue"],
        "TPE1": ["Artist"],
        "TALB": ["Album"],
        "TRCK": ["1/10"],
    }


class EmptyAudio(FakeAudio):
    tags = {}


def test_read_mp3_extracts_metadata(monkeypatch) -> None:
    """
    test_read_mp3_extracts_metadata: verifica leitura das tags.

    input:
        objeto MP3 simulado com tags e propriedades técnicas.

    output:
        None, teste aprovado quando MusicTrack contém os dados esperados.
    """
    monkeypatch.setattr(keef.music, "MP3", lambda path: FakeAudio())

    track = keef.music.read_mp3(Path("music.mp3"))

    assert track == MusicTrack(
        path="music.mp3",
        title="Blue",
        artist="Artist",
        album="Album",
        track_number=1,
        duration_seconds=210.5,
        bitrate_kbps=320,
    )


def test_read_mp3_reports_missing_metadata(monkeypatch) -> None:
    """
    test_read_mp3_reports_missing_metadata: identifica tags ausentes.

    input:
        objeto MP3 simulado sem tags.

    output:
        None, teste aprovado quando os nomes ausentes são listados.
    """
    monkeypatch.setattr(keef.music, "MP3", lambda path: EmptyAudio())

    track = keef.music.read_mp3(Path("music.mp3"))

    assert track.missing_metadata == ["title", "artist", "album", "track_number"]


def test_read_mp3_uses_filename_fallback(monkeypatch) -> None:
    """
    test_read_mp3_uses_filename_fallback: usa nome estruturado sem tags.

    input:
        MP3 sem tags com nome contendo faixa, artista e título.

    output:
        None, teste aprovado quando metadados básicos são recuperados.
    """
    monkeypatch.setattr(keef.music, "MP3", lambda path: EmptyAudio())

    track = keef.music.read_mp3(Path("02. Brent Faiyaz - LOOSE CHANGE.mp3"))

    assert track.track_number == 2
    assert track.artist == "Brent Faiyaz"
    assert track.title == "LOOSE CHANGE"
    assert track.missing_metadata == ["album"]


def test_try_read_mp3_returns_error_for_missing_file() -> None:
    """
    test_try_read_mp3_returns_error_for_missing_file: trata caminho ausente.

    input:
        caminho que não existe.

    output:
        None, teste aprovado quando uma mensagem de erro é retornada.
    """
    result = keef.music.try_read_mp3(Path("missing.mp3"))

    assert isinstance(result, str)
    assert "Arquivo não encontrado" in result


def test_read_mp3_propagates_invalid_file_error(monkeypatch, tmp_path) -> None:
    """
    test_read_mp3_propagates_invalid_file_error: preserva falha do parser.

    input:
        parser MP3 simulado que lança erro.

    output:
        None, teste aprovado quando o erro é convertido por try_read_mp3.
    """
    def invalid_mp3(path: Path):
        """
        invalid_mp3: simula arquivo MP3 inválido.

        input:
            path, caminho recebido pelo parser.

        output:
            None, sempre lança uma exceção de leitura.
        """
        raise OSError("invalid mp3")

    monkeypatch.setattr(keef.music, "MP3", invalid_mp3)
    invalid_path = tmp_path / "invalid.mp3"
    invalid_path.touch()

    result = keef.music.try_read_mp3(invalid_path)

    assert isinstance(result, str)
    assert "Não foi possível ler" in result
