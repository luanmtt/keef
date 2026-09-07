import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from keef.matching import match_album, score_candidate
from keef.models import (
    AlbumMatchResult,
    AlbumScan,
    BatchPreviewItem,
    MetadataReport,
    MusicTrack,
    QualityPolicy,
    SearchCandidate,
)
from keef.quality import evaluate_candidate_quality

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def load_metadata_report(path: Path) -> MetadataReport:
    """
    load_metadata_report: carrega relatório JSON do scan.

    input:
        path, caminho de metadata.json.

    output:
        MetadataReport, tracks e erros validados.
    """
    return MetadataReport.model_validate(json.loads(path.read_text()))


def preview_batch(
    report: MetadataReport,
    candidate_provider: Callable[[MusicTrack], list[SearchCandidate]],
    policy: QualityPolicy,
    target_kbps: int | None = None,
    search_delay_seconds: float = 1.0,
) -> list[BatchPreviewItem]:
    """
    preview_batch: cria decisões batch sem iniciar downloads.

    input:
        report, tracks carregadas do relatório.
        candidate_provider, função sequencial de pesquisa.
        policy, regra de qualidade do candidato.
        target_kbps, bitrate alvo opcional.
        search_delay_seconds, pausa entre pesquisas para evitar 409 do slskd.

    output:
        list[BatchPreviewItem], resultados individuais e erros preservados.
    """
    preview = []

    for index, track in enumerate(report.tracks):
        try:
            candidates = candidate_provider(track)
            matches = [score_candidate(track, candidate) for candidate in candidates]
            decisions = [
                evaluate_candidate_quality(track, match.candidate, policy, target_kbps)
                for match in matches
            ]
            preview.append(
                BatchPreviewItem(
                    track=track,
                    candidates=matches,
                    quality_decisions=decisions,
                )
            )
        except (httpx.HTTPError, OSError, TypeError, ValueError) as error:
            preview.append(BatchPreviewItem(track=track, error=str(error)))

        if index < len(report.tracks) - 1 and search_delay_seconds > 0:
            time.sleep(search_delay_seconds)

    return preview


def preview_albums(
    albums: list[AlbumScan],
    search_provider: Callable[[AlbumScan], list[dict[str, Any]]],
    policy: QualityPolicy,
    target_kbps: int | None = None,
    track_count_tolerance: int = 1,
    search_delay_seconds: float = 1.0,
) -> list[AlbumMatchResult]:
    """
    preview_albums: pesquisa candidatos para álbuns completos.

    input:
        albums, lista de álbuns escaneados.
        search_provider, função que retorna respostas brutas do slskd.
        policy, regra de qualidade do candidato.
        target_kbps, bitrate alvo opcional.
        track_count_tolerance, diferença aceitável no número de faixas.
        search_delay_seconds, pausa entre pesquisas.

    output:
        list[AlbumMatchResult], resultados por álbum.
    """
    results = []

    for index, album in enumerate(albums):
        try:
            responses = search_provider(album)
            result = match_album(
                album,
                responses,
                policy,
                target_kbps,
                track_count_tolerance,
            )
            results.append(result)
        except (httpx.HTTPError, OSError, TypeError, ValueError) as error:
            results.append(AlbumMatchResult(album=album, error=str(error)))

        if index < len(albums) - 1 and search_delay_seconds > 0:
            time.sleep(search_delay_seconds)

    return results

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
