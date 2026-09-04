from keef.models import MusicTrack, QualityPolicy, SearchCandidate
from keef.quality import evaluate_mp3_quality

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def build_quality_track() -> MusicTrack:
    """
    build_quality_track: cria track MP3 para testes de qualidade.

    input:
        nenhum.

    output:
        MusicTrack, track com bitrate atual conhecido.
    """
    return MusicTrack(path="song.mp3", bitrate_kbps=192)


def build_quality_candidate(bitrate_kbps: int) -> SearchCandidate:
    """
    build_quality_candidate: cria candidato MP3 com bitrate informado.

    input:
        bitrate_kbps, bitrate do candidato.

    output:
        SearchCandidate, candidato pronto para avaliação.
    """
    return SearchCandidate(
        username="alice",
        filename="song.mp3",
        size=1000,
        bitrate_kbps=bitrate_kbps,
        format="mp3",
    )


def test_higher_policy_accepts_larger_bitrate() -> None:
    """
    test_higher_policy_accepts_larger_bitrate: testa política higher.

    input:
        track 192 kbps e candidato 320 kbps.

    output:
        None, teste aprovado quando candidato é elegível.
    """
    decision = evaluate_mp3_quality(
        build_quality_track(),
        build_quality_candidate(320),
        QualityPolicy.HIGHER,
    )

    assert decision.eligible is True


def test_lower_policy_accepts_smaller_bitrate() -> None:
    """
    test_lower_policy_accepts_smaller_bitrate: testa política lower.

    input:
        track 192 kbps e candidato 128 kbps.

    output:
        None, teste aprovado quando candidato é elegível.
    """
    decision = evaluate_mp3_quality(
        build_quality_track(),
        build_quality_candidate(128),
        QualityPolicy.LOWER,
    )

    assert decision.eligible is True


def test_exact_policy_requires_target() -> None:
    """
    test_exact_policy_requires_target: testa política exact.

    input:
        candidato 256 kbps e alvo 256 kbps.

    output:
        None, teste aprovado quando bitrate coincide.
    """
    decision = evaluate_mp3_quality(
        build_quality_track(),
        build_quality_candidate(256),
        QualityPolicy.EXACT,
        target_kbps=256,
    )

    assert decision.eligible is True
