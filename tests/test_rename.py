from pathlib import Path
from typing import cast

from keef.models import MusicTrack
from keef.rename import (
    AUDIO_EXTENSIONS,
    build_target_stem,
    plan_renames,
    sanitize_name,
    unique_destination,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_sanitize_name_removes_invalid_characters() -> None:
    """
    test_sanitize_name_removes_invalid_characters: remove caracteres proibidos.

    input:
        nome com caracteres inválidos de filesystem.

    output:
        None, teste aprovado quando o nome limpo mantém apenas o útil.
    """
    result = sanitize_name('Dr?eem*/: <The> "Song"')

    assert result == "Dreem The Song"


def test_sanitize_name_collapses_whitespace() -> None:
    """
    test_sanitize_name_collapses_whitespace: normaliza espaços repetidos.

    input:
        nome com espaços e tabulações consecutivas.

    output:
        None, teste aprovado quando os espaços são reduzidos a um único.
    """
    result = sanitize_name("Artist  \t  Song")

    assert result == "Artist Song"


def test_build_target_stem_individual_track() -> None:
    """
    test_build_target_stem_individual_track: monta formato sem número.

    input:
        track sem track_number.

    output:
        None, teste aprovado quando o stem é '{titulo} - {artista}'.
    """
    track = MusicTrack(path="x.flac", title="Lluvia", artist="Analog Africa")

    stem = build_target_stem(track)

    assert stem == "Lluvia - Analog Africa"


def test_build_target_stem_album_track() -> None:
    """
    test_build_target_stem_album_track: monta formato com número de faixa.

    input:
        track com track_number definido.

    output:
        None, teste aprovado quando o stem é '{nn}. {titulo} - {artista}'.
    """
    track = MusicTrack(
        path="x.mp3",
        title="What Do You See",
        artist="Wire",
        track_number=9,
    )

    stem = build_target_stem(track)

    assert stem == "09. What Do You See - Wire"


def test_build_target_stem_uses_two_digit_padding() -> None:
    """
    test_build_target_stem_uses_two_digit_padding: usa zero à esquerda.

    input:
        track com track_number 2.

    output:
        None, teste aprovado quando o número tem dois dígitos.
    """
    track = MusicTrack(path="x.flac", title="Lluvia", track_number=2)

    stem = build_target_stem(track)

    assert stem == "02. Lluvia"


def test_build_target_stem_returns_none_without_title() -> None:
    """
    test_build_target_stem_returns_none_without_title: trata falta de título.

    input:
        track sem title.

    output:
        None, teste aprovado quando o stem é None.
    """
    track = MusicTrack(path="x.mp3", artist="Wire")

    assert build_target_stem(track) is None


def test_build_target_stem_without_artist() -> None:
    """
    test_build_target_stem_without_artist: monta stem apenas com título.

    input:
        track com título e sem artista.

    output:
        None, teste aprovado quando o stem é apenas o título.
    """
    track = MusicTrack(path="x.flac", title="Lluvia")

    stem = build_target_stem(track)

    assert stem == "Lluvia"


def test_unique_destination_adds_numeric_suffix_on_collision() -> None:
    """
    test_unique_destination_adds_numeric_suffix_on_collision: resolve colisão.

    input:
        diretório com nome já reservado.

    output:
        None, teste aprovado quando o destino recebe sufixo (1).
    """
    used = {"Song - Artist.flac"}

    destination = unique_destination(Path("."), "Song - Artist", ".flac", used)

    assert destination == Path("Song - Artist (1).flac")
    assert "Song - Artist (1).flac" in used


def test_unique_destination_increments_suffix() -> None:
    """
    test_unique_destination_increments_suffix: incrementa sufixo em colisões.

    input:
        diretório com dois nomes reservados.

    output:
        None, teste aprovado quando o destino é o terceiro nome.
    """
    used = {"Song - Artist.flac", "Song - Artist (1).flac"}

    destination = unique_destination(Path("."), "Song - Artist", ".flac", used)

    assert destination == Path("Song - Artist (2).flac")


def test_plan_renames_skips_non_audio_files(tmp_path, monkeypatch) -> None:
    """
    test_plan_renames_skips_non_audio_files: ignora arquivos não-audio.

    input:
        diretório com arquivo .txt e um .mp3 válido.

    output:
        None, teste aprovado quando apenas o áudio é planejado.
    """
    (tmp_path / "notes.txt").write_text("olá")
    (tmp_path / "01 - Intro.mp3").write_bytes(b"fake")

    def fake_read_audio(path):
        """
        fake_read_audio: retorna metadados fixos para qualquer áudio.

        input:
            path, caminho do arquivo.

        output:
            MusicTrack, metadados simulados.
        """
        return MusicTrack(
            path=str(path),
            title="Intro",
            artist="Banda",
            track_number=1,
        )

    monkeypatch.setattr("keef.rename.read_audio", fake_read_audio)

    entries = plan_renames(tmp_path)

    assert len(entries) == 1
    assert entries[0]["reason"] == "renomear"
    destination = cast(str, entries[0]["destination"])
    assert Path(destination).name == "01. Intro - Banda.mp3"


def test_plan_renames_keeps_already_formatted(tmp_path, monkeypatch) -> None:
    """
    test_plan_renames_keeps_already_formatted: preserva nome já correto.

    input:
        diretório com arquivo já no formato padrão.

    output:
        None, teste aprovado quando o destino é o próprio arquivo.
    """
    (tmp_path / "09. What Do You See - Wire.mp3").write_bytes(b"fake")

    def fake_read_audio(path):
        """
        fake_read_audio: retorna metadados fixos.

        input:
            path, caminho do arquivo.

        output:
            MusicTrack, metadados simulados.
        """
        return MusicTrack(
            path=str(path),
            title="What Do You See",
            artist="Wire",
            track_number=9,
        )

    monkeypatch.setattr("keef.rename.read_audio", fake_read_audio)

    entries = plan_renames(tmp_path)

    assert len(entries) == 1
    assert entries[0]["reason"] == "já está no formato"
    assert entries[0]["destination"] == str(
        tmp_path / "09. What Do You See - Wire.mp3"
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━