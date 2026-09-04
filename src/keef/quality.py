from keef.models import MusicTrack, QualityDecision, QualityPolicy, SearchCandidate

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def evaluate_mp3_quality(
    track: MusicTrack,
    candidate: SearchCandidate,
    policy: QualityPolicy,
    target_kbps: int | None = None,
) -> QualityDecision:
    """
    evaluate_mp3_quality: avalia bitrate de candidato MP3.

    input:
        track, música local com bitrate atual.
        candidate, resultado remoto com bitrate candidato.
        policy, regra higher, lower ou exact.
        target_kbps, bitrate exato opcional para comparação.

    output:
        QualityDecision, elegibilidade e motivo da decisão.
    """
    if candidate.format != "mp3":
        return QualityDecision(eligible=False, reason="formato diferente de MP3")

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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
