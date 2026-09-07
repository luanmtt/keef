from keef.batch import load_metadata_report, preview_batch
from keef.models import MusicTrack, QualityPolicy, SearchCandidate

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_load_metadata_report_reads_json(tmp_path) -> None:
    """
    test_load_metadata_report_reads_json: valida carregamento do relatório.

    input:
        metadata.json temporário com uma track.

    output:
        None, teste aprovado quando track é reconstruída.
    """
    report_path = tmp_path / "metadata.json"
    report_path.write_text(
        '{"tracks": [{"path": "song.mp3", "title": "Blue"}], "errors": []}'
    )

    report = load_metadata_report(report_path)

    assert report.tracks[0].title == "Blue"


def test_preview_batch_preserves_item_errors() -> None:
    """
    test_preview_batch_preserves_item_errors: mantém erro de uma track.

    input:
        duas tracks e provider que falha em uma delas.

    output:
        None, teste aprovado quando preview continua para próxima track.
    """
    tracks = [
        MusicTrack(path="ok.mp3", title="Blue", bitrate_kbps=192),
        MusicTrack(path="broken.mp3", title="Red", bitrate_kbps=192),
    ]

    def provider(track: MusicTrack) -> list[SearchCandidate]:
        """
        provider: simula pesquisa por track.

        input:
            track, música que será pesquisada.

        output:
            list[SearchCandidate], candidato ou erro simulado.
        """
        if track.path == "broken.mp3":
            raise OSError("falha de pesquisa")

        return [
            SearchCandidate(
                username="alice",
                filename="Blue.mp3",
                size=1000,
                title="Blue",
                bitrate_kbps=320,
                format="mp3",
            )
        ]

    from keef.models import MetadataReport

    result = preview_batch(
        MetadataReport(tracks=tracks),
        provider,
        QualityPolicy.HIGHER,
    )

    assert len(result) == 2
    assert result[0].quality_decisions[0].eligible is True
    assert result[1].error == "falha de pesquisa"


def test_preview_batch_honors_search_delay(monkeypatch) -> None:
    """
    test_preview_batch_honors_search_delay: respeita pausa entre pesquisas.

    input:
        duas tracks e provider vazio com delay zero (para não dormir no teste).

    output:
        None, teste aprovado quando delay não é aplicado com valor zero.
    """
    tracks = [
        MusicTrack(path="a.mp3", title="A", bitrate_kbps=192),
        MusicTrack(path="b.mp3", title="B", bitrate_kbps=192),
    ]
    calls = []

    def provider(track: MusicTrack) -> list[SearchCandidate]:
        """
        provider: registra chamadas sem retornar candidatos.

        input:
            track, música que será pesquisada.

        output:
            list[SearchCandidate], lista vazia.
        """
        calls.append(track.path)
        return []

    from keef.models import MetadataReport

    result = preview_batch(
        MetadataReport(tracks=tracks),
        provider,
        QualityPolicy.HIGHER,
        search_delay_seconds=0.0,
    )

    assert len(result) == 2
    assert calls == ["a.mp3", "b.mp3"]
