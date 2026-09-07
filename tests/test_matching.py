from keef.matching import match_album, normalize_text, score_candidate
from keef.models import AlbumScan, MusicTrack, QualityPolicy, SearchCandidate

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def build_track() -> MusicTrack:
    """
    build_track: cria música local para os testes.

    input:
        nenhum.

    output:
        MusicTrack, música com metadados conhecidos.
    """
    return MusicTrack(
        path="local/blue.mp3",
        title="Bélue!",
        artist="The Artist",
        album="The Album",
        duration_seconds=210,
    )


def build_candidate(**values) -> SearchCandidate:
    """
    build_candidate: cria candidato remoto para os testes.

    input:
        values, campos opcionais para substituir no candidato padrão.

    output:
        SearchCandidate, candidato normalizado para avaliação.
    """
    defaults = {
        "username": "alice",
        "filename": "The Artist - Bélue!.mp3",
        "size": 8_000_000,
        "title": "Bélue!",
        "artist": "The Artist",
        "album": "The Album",
        "duration_seconds": 210,
    }
    defaults.update(values)

    return SearchCandidate.model_validate(defaults)


def test_normalize_text_removes_accents_and_punctuation() -> None:
    """
    test_normalize_text_removes_accents_and_punctuation: verifica normalização.

    input:
        texto com acentos, pontuação e espaços.

    output:
        None, teste aprovado quando o texto é comparável.
    """
    assert normalize_text("  BéluE!  ") == "belue"


def test_score_candidate_accepts_matching_metadata() -> None:
    """
    test_score_candidate_accepts_matching_metadata: aceita metadados equivalentes.

    input:
        música local e candidato com dados correspondentes.

    output:
        None, teste aprovado quando candidato é aceito.
    """
    result = score_candidate(build_track(), build_candidate())

    assert result.accepted is True
    assert result.ambiguous is False
    assert result.score > 0.99


def test_score_candidate_rejects_misleading_compilation() -> None:
    """
    test_score_candidate_rejects_misleading_compilation: rejeita caminho enganoso.

    input:
        título desejado e compilação que apenas contém o termo no caminho.

    output:
        None, teste aprovado quando candidato é rejeitado.
    """
    candidate = build_candidate(
        filename="Cowboy Bebop Blue Soundtrack 01. Blue.mp3",
        title="Cowboy Bebop Blue Soundtrack 01. Blue",
        artist=None,
        album=None,
        duration_seconds=400,
    )

    result = score_candidate(build_track(), candidate)

    assert result.accepted is False
    assert result.score < 0.65


def test_score_candidate_marks_close_competition_ambiguous() -> None:
    """
    test_score_candidate_marks_close_competition_ambiguous: marca empate próximo.

    input:
        candidato com score próximo de outro resultado.

    output:
        None, teste aprovado quando confirmação manual é exigida.
    """
    result = score_candidate(
        build_track(),
        build_candidate(),
        competing_score=0.99,
    )

    assert result.accepted is False
    assert result.ambiguous is True


def test_candidates_from_responses_uses_filename_as_title() -> None:
    """
    test_candidates_from_responses_uses_filename_as_title: converte resposta remota.

    input:
        resposta com usuário e arquivo sem tags textuais.

    output:
        None, teste aprovado quando campos básicos são extraídos.
    """
    from keef.matching import candidates_from_responses

    candidates = candidates_from_responses(
        [
            {
                "username": "alice",
                "files": [{"filename": "Artist - Blue.mp3", "size": 1000}],
            }
        ]
    )

    assert candidates[0].title == "Artist - Blue"
    assert candidates[0].format == "mp3"


def test_match_album_matches_tracks_by_title() -> None:
    """
    test_match_album_matches_tracks_by_title: compara faixas por título.

    input:
        álbum local com 2 faixas e respostas com 2 arquivos do mesmo usuário.

    output:
        None, teste aprovado quando faixas são pareadas por título.
    """
    album = AlbumScan(
        folder_name="Blonde",
        artist="Frank Ocean",
        album="Blonde",
        tracks=[
            MusicTrack(path="01 Nikes.flac", title="Nikes", artist="Frank Ocean"),
            MusicTrack(path="02 Ivy.flac", title="Ivy", artist="Frank Ocean"),
        ],
        track_count=2,
    )

    responses = [
        {
            "username": "bob",
            "files": [
                {
                    "filename": "/music/Frank Ocean - Blonde/01 Nikes.flac",
                    "size": 50_000_000,
                    "title": "Nikes",
                    "artist": "Frank Ocean",
                    "bitrate": 1411,
                },
                {
                    "filename": "/music/Frank Ocean - Blonde/02 Ivy.flac",
                    "size": 40_000_000,
                    "title": "Ivy",
                    "artist": "Frank Ocean",
                    "bitrate": 1411,
                },
            ],
        }
    ]

    result = match_album(album, responses, QualityPolicy.HIGHER)

    assert len(result.matches) == 1
    assert result.matches[0].username == "bob"
    assert len(result.matches[0].matched_files) == 2
    assert result.matches[0].overall_score > 0.8


def test_match_album_rejects_wrong_track_count() -> None:
    """
    test_match_album_rejects_wrong_track_count: rejeita com contagem errada.

    input:
        álbum local com 2 faixas e resposta com 5 arquivos.

    output:
        None, teste aprovado quando usuário com contagem diferente é ignorado.
    """
    album = AlbumScan(
        folder_name="Blonde",
        artist="Frank Ocean",
        album="Blonde",
        tracks=[
            MusicTrack(path="01 Nikes.flac", title="Nikes"),
            MusicTrack(path="02 Ivy.flac", title="Ivy"),
        ],
        track_count=2,
    )

    responses = [
        {
            "username": "bob",
            "files": [
                {"filename": f"/music/0{i}.flac", "size": 10_000, "title": f"T{i}"}
                for i in range(5)
            ],
        }
    ]

    result = match_album(album, responses, QualityPolicy.HIGHER, track_count_tolerance=1)

    assert len(result.matches) == 0


def test_match_album_returns_empty_for_no_responses() -> None:
    """
    test_match_album_returns_empty_for_no_responses: lida com respostas vazias.

    input:
        álbum local e lista de respostas vazia.

    output:
        None, teste aprovado quando resultado não tem matches.
    """
    album = AlbumScan(
        folder_name="Test",
        tracks=[MusicTrack(path="01.flac", title="A")],
        track_count=1,
    )

    result = match_album(album, [], QualityPolicy.HIGHER)

    assert len(result.matches) == 0
    assert result.error is None
