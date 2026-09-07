from keef.models import MusicTrack, QualityDecision, QualityPolicy, SearchCandidate

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def evaluate_candidate_quality(
    track: MusicTrack,
    candidate: SearchCandidate,
    policy: QualityPolicy,
    target_kbps: int | None = None,
) -> QualityDecision:
    """
    evaluate_candidate_quality: avalia bitrate e formato do candidato.

    input:
        track, música local com bitrate/formato atual.
        candidate, resultado remoto com bitrate/formato candidato.
        policy, regra higher, lower ou exact.
        target_kbps, bitrate exato opcional para comparação.

    output:
        QualityDecision, elegibilidade e motivo da decisão.
    """
    if track.bitrate_kbps is None or candidate.bitrate_kbps is None:
        return QualityDecision(eligible=False, reason="bitrate ausente")

    if policy is QualityPolicy.HIGHER:
        eligible = candidate.bitrate_kbps > track.bitrate_kbps
        reason = "bitrate maior" if eligible else "bitrate não é maior"
    elif policy is QualityPolicy.LOWER:
        eligible = candidate.bitrate_kbps < track.bitrate_kbps
        reason = "bitrate menor" if eligible else "bitrate não é menor"
    else:
        expected = target_kbps if target_kbps is not None else track.bitrate_kbps
        eligible = candidate.bitrate_kbps == expected
        reason = "bitrate exato" if eligible else f"bitrate diferente de {expected} kbps"

    return QualityDecision(eligible=eligible, reason=reason)


def evaluate_mp3_quality(
    track: MusicTrack,
    candidate: SearchCandidate,
    policy: QualityPolicy,
    target_kbps: int | None = None,
) -> QualityDecision:
    """
    evaluate_mp3_quality: mantém compatibilidade com nome antigo.

    input:
        track, música local com bitrate atual.
        candidate, resultado remoto com bitrate candidato.
        policy, regra higher, lower ou exact.
        target_kbps, bitrate exato opcional para comparação.

    output:
        QualityDecision, delegada para evaluate_candidate_quality.
    """
    return evaluate_candidate_quality(track, candidate, policy, target_kbps)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
