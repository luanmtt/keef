from pathlib import Path

import keef.music
from keef.models import MusicTrack

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class FakeInfo:
    length = 210.5
    bitrate = 320000
    sample_rate = 44100
    channels = 2


class FakeAudio:
    info = FakeInfo()
    tags = {
        "title": ["Blue"],
        "artist": ["Artist"],
        "album": ["Album"],
        "tracknumber": ["1/10"],
    }
    __class__ = type("MP3", (), {})


class EmptyAudio(FakeAudio):
    tags = {}
    __class__ = type("MP3", (), {})


class FakeFlacAudio(FakeAudio):
    tags = {
        "title": ["Green"],
        "artist": ["Flac Artist"],
        "album": ["Flac Album"],
        "tracknumber": ["3"],
    }
    __class__ = type("FLAC", (), {})


def _make_mutagen_stub(audio: object):
    """
    _make_mutagen_stub: cria stub para MutagenFile.

    input:
        audio, instância de áudio simulada.

    output:
        function, lambda que retorna o áudio simulado.
    """
    return lambda path, easy=True: audio


def test_read_audio_extracts_metadata(monkeypatch) -> None:
    """
    test_read_audio_extracts_metadata: verifica leitura das tags.

    input:
        objeto de áudio simulado com tags e propriedades técnicas.

    output:
        None, teste aprovado quando MusicTrack contém os dados esperados.
    """
    monkeypatch.setattr(keef.music, "MutagenFile", _make_mutagen_stub(FakeAudio()))

    track = keef.music.read_audio(Path("music.mp3"))

    assert track == MusicTrack(
        path="music.mp3",
        format="mp3",
        codec="MP3",
        title="Blue",
        artist="Artist",
        album="Album",
        track_number=1,
        duration_seconds=210.0,
        bitrate_kbps=320,
        sample_rate_hz=44100,
        channels=2,
        lossless=False,
    )


def test_read_audio_detects_lossless(monkeypatch) -> None:
    """
    test_read_audio_detects_lossless: identifica FLAC como lossless.

    input:
        objeto FLAC simulado.

    output:
        None, teste aprovado quando lossless é True.
    """
    monkeypatch.setattr(keef.music, "MutagenFile", _make_mutagen_stub(FakeFlacAudio()))

    track = keef.music.read_audio(Path("music.flac"))

    assert track.format == "flac"
    assert track.codec == "FLAC"
    assert track.lossless is True
    assert track.bitrate_kbps == 320


def test_read_audio_reports_missing_metadata(monkeypatch) -> None:
    """
    test_read_audio_reports_missing_metadata: identifica tags ausentes.

    input:
        objeto de áudio simulado sem tags.

    output:
        None, teste aprovado quando os nomes ausentes são listados.
    """
    monkeypatch.setattr(keef.music, "MutagenFile", _make_mutagen_stub(EmptyAudio()))

    track = keef.music.read_audio(Path("music.mp3"))

    assert track.missing_metadata == ["title", "artist", "album", "track_number"]


def test_read_audio_uses_filename_fallback(monkeypatch) -> None:
    """
    test_read_audio_uses_filename_fallback: usa nome estruturado sem tags.

    input:
        áudio sem tags com nome contendo faixa, artista e título.

    output:
        None, teste aprovado quando metadados básicos são recuperados.
    """
    monkeypatch.setattr(keef.music, "MutagenFile", _make_mutagen_stub(EmptyAudio()))

    track = keef.music.read_audio(Path("02. Brent Faiyaz - LOOSE CHANGE.mp3"))

    assert track.track_number == 2
    assert track.artist == "Brent Faiyaz"
    assert track.title == "LOOSE CHANGE"
    assert track.missing_metadata == ["album"]


def test_try_read_audio_returns_error_for_missing_file() -> None:
    """
    test_try_read_audio_returns_error_for_missing_file: trata caminho ausente.

    input:
        caminho que não existe.

    output:
        None, teste aprovado quando uma mensagem de erro é retornada.
    """
    result = keef.music.try_read_audio(Path("missing.mp3"))

    assert isinstance(result, str)
    assert "Arquivo não encontrado" in result


def test_try_read_audio_propagates_invalid_file_error(monkeypatch, tmp_path) -> None:
    """
    test_try_read_audio_propagates_invalid_file_error: preserva falha do parser.

    input:
        parser simulado que lança erro.

    output:
        None, teste aprovado quando o erro é convertido por try_read_audio.
    """
    def invalid_audio(path: Path, easy: bool = True):
        """
        invalid_audio: simula arquivo de áudio inválido.

        input:
            path, caminho recebido pelo parser.
            easy, modo de parsing easy.

        output:
            None, sempre lança uma exceção de leitura.
        """
        raise OSError("invalid audio")

    monkeypatch.setattr(keef.music, "MutagenFile", invalid_audio)
    invalid_path = tmp_path / "invalid.mp3"
    invalid_path.touch()

    result = keef.music.try_read_audio(invalid_path)

    assert isinstance(result, str)
    assert "Não foi possível ler" in result


def test_read_audio_returns_unknown_when_detection_fails(monkeypatch, tmp_path) -> None:
    """
    test_read_audio_returns_unknown_when_detection_fails: rejeita formato não reconhecido.

    input:
        parser simulado que retorna None.

    output:
        None, teste aprovado quando try_read_audio retorna mensagem de erro.
    """
    monkeypatch.setattr(keef.music, "MutagenFile", lambda path, easy=True: None)
    unknown_path = tmp_path / "unknown.bin"
    unknown_path.write_bytes(b"not audio")

    result = keef.music.try_read_audio(unknown_path)

    assert isinstance(result, str)
    assert "formato de áudio não reconhecido" in result

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
