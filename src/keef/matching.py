import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from keef.models import (
    AlbumFileMatch,
    AlbumMatch,
    AlbumMatchResult,
    AlbumScan,
    MatchResult,
    MusicTrack,
    QualityDecision,
    QualityPolicy,
    SearchCandidate,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def normalize_text(value: str | None) -> str:
    """
    normalize_text: normaliza texto para comparação.

    input:
        value, texto opcional de metadados.

    output:
        str, texto sem acentos, pontuação ou espaços inconsistentes.
    """
    if not value:
        return ""

    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )

    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", without_accents.lower())).strip()


def _text_score(left: str | None, right: str | None) -> float | None:
    """
    _text_score: calcula similaridade textual.

    input:
        left, primeiro texto opcional.
        right, segundo texto opcional.

    output:
        float | None, score entre zero e um ou None quando falta um valor.
    """
    normalized_left = normalize_text(left)
    normalized_right = normalize_text(right)

    if not normalized_left or not normalized_right:
        return None

    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


def _duration_score(left: float | None, right: float | None) -> float | None:
    """
    _duration_score: compara durações com tolerância de segundos.

    input:
        left, duração local em segundos.
        right, duração candidata em segundos.

    output:
        float | None, score entre zero e um ou None quando falta duração.
    """
    if left is None or right is None:
        return None

    difference = abs(left - right)

    if difference <= 2:
        return 1.0

    if difference >= 30:
        return 0.0

    return 1 - (difference - 2) / 28


def _weighted_score(scores: dict[str, float | None]) -> float:
    """
    _weighted_score: combina scores disponíveis por peso.

    input:
        scores, similaridades nomeadas dos metadados.

    output:
        float, score combinado entre zero e um.
    """
    weights = {
        "title": 0.5,
        "artist": 0.3,
        "album": 0.1,
        "duration": 0.1,
    }
    available = {
        name: value for name, value in scores.items() if value is not None
    }

    if not available:
        return 0.0

    total_weight = sum(weights[name] for name in available)

    return sum(weights[name] * value for name, value in available.items()) / total_weight


def score_candidate(
    track: MusicTrack,
    candidate: SearchCandidate,
    threshold: float = 0.65,
    ambiguity_delta: float = 0.05,
    competing_score: float | None = None,
) -> MatchResult:
    """
    score_candidate: avalia correspondência de música de forma explicável.

    input:
        track, metadados da música local.
        candidate, resultado remoto normalizado.
        threshold, score mínimo para aceitação.
        ambiguity_delta, distância mínima do segundo resultado.
        competing_score, score do candidato concorrente mais próximo.

    output:
        MatchResult, score, decisão e motivos da avaliação.
    """
    scores = {
        "title": _text_score(track.title, candidate.title),
        "artist": _text_score(track.artist, candidate.artist),
        "album": _text_score(track.album, candidate.album),
        "duration": _duration_score(track.duration_seconds, candidate.duration_seconds),
    }
    score = _weighted_score(scores)
    reasons = [
        f"{name}: {value:.2f}"
        for name, value in scores.items()
        if value is not None
    ]
    ambiguous = (
        competing_score is not None
        and abs(score - competing_score) < ambiguity_delta
    )
    accepted = score >= threshold and not ambiguous

    if score < threshold:
        reasons.append(f"score abaixo do limiar {threshold:.2f}")

    if ambiguous:
        reasons.append("score próximo de outro candidato")

    return MatchResult(
        candidate=candidate,
        score=score,
        accepted=accepted,
        ambiguous=ambiguous,
        reasons=reasons,
    )


def candidates_from_responses(
    responses: list[dict[str, Any]],
) -> list[SearchCandidate]:
    """
    candidates_from_responses: converte respostas do slskd em candidatos.

    input:
        responses, objetos JSON retornados pela pesquisa.

    output:
        list[SearchCandidate], arquivos remotos utilizáveis pelo matcher.
    """
    candidates = []

    for response in responses:
        username = response.get("username") or response.get("Username")
        files = response.get("files") or response.get("Files") or []

        if not isinstance(username, str) or not isinstance(files, list):
            continue

        for file_data in files:
            if not isinstance(file_data, dict):
                continue

            filename = file_data.get("filename") or file_data.get("Filename")
            size = file_data.get("size") or file_data.get("Size")

            if not isinstance(filename, str) or not isinstance(size, int):
                continue

            title = file_data.get("title") or file_data.get("Title")

            if not isinstance(title, str):
                title = Path(filename).stem

            candidates.append(
                SearchCandidate.model_validate(
                    {
                        "username": username,
                        "filename": filename,
                        "size": size,
                        "title": title,
                        "artist": file_data.get("artist") or file_data.get("Artist"),
                        "album": file_data.get("album") or file_data.get("Album"),
                        "duration_seconds": file_data.get("duration")
                        or file_data.get("Length"),
                        "bitrate_kbps": file_data.get("bitrate")
                        or file_data.get("Bitrate"),
                        "format": Path(filename).suffix.removeprefix(".").lower(),
                    }
                )
            )

    return candidates


def match_album(
    album: AlbumScan,
    responses: list[dict[str, Any]],
    policy: QualityPolicy,
    target_kbps: int | None = None,
    track_count_tolerance: int = 1,
    min_match_score: float = 0.65,
) -> AlbumMatchResult:
    """
    match_album: compara faixas remotas de um álbum contra as locais.

    input:
        album, scan local do álbum com faixas esperadas.
        responses, respostas brutas do slskd (cada uma com username e files).
        policy, regra de qualidade (higher, lower, exact).
        target_kbps, bitrate alvo opcional para policy=exact.
        track_count_tolerance, diferença máxima aceitável no número de faixas.
        min_match_score, score mínimo para aceitar uma faixa individual.

    output:
        AlbumMatchResult, matches ordenados por score (melhor primeiro).
    """
    from keef.quality import evaluate_candidate_quality

    users: dict[str, list[dict[str, Any]]] = {}

    for response in responses:
        username = response.get("username") or response.get("Username")

        if not isinstance(username, str):
            continue

        files = response.get("files") or response.get("Files") or []

        if not isinstance(files, list):
            continue

        for file_data in files:
            if isinstance(file_data, dict):
                users.setdefault(username, []).append(file_data)

    expected_count = album.track_count
    album_matches: list[AlbumMatch] = []

    for username, file_list in users.items():
        if abs(len(file_list) - expected_count) > track_count_tolerance:
            continue

        remaining_files = list(file_list)
        matched_files: list[AlbumFileMatch] = []
        unmatched_locals: list[str] = []

        for local_track in album.tracks:
            best_score = 0.0
            best_file = None

            for file_data in remaining_files:
                candidate = _candidate_from_file(username, file_data)

                if candidate is None:
                    continue

                score = _text_score(local_track.title, candidate.title) or 0.0
                artist_score = _text_score(local_track.artist, candidate.artist)

                if artist_score is not None:
                    score = score * 0.7 + artist_score * 0.3

                if score > best_score:
                    best_score = score
                    best_file = (file_data, candidate)

            if best_file is not None and best_score >= min_match_score:
                file_data, candidate = best_file
                quality = evaluate_candidate_quality(
                    local_track, candidate, policy, target_kbps
                )
                matched_files.append(
                    AlbumFileMatch(
                        local_track=local_track,
                        remote_filename=candidate.filename,
                        remote_size=candidate.size,
                        score=best_score,
                        quality=quality,
                    )
                )
                remaining_files.remove(file_data)
            else:
                unmatched_locals.append(local_track.path)

        if matched_files:
            overall = sum(m.score for m in matched_files) / len(matched_files)
            accepted = (
                len(unmatched_locals) == 0
                and all(m.quality.eligible for m in matched_files)
            )
            album_matches.append(
                AlbumMatch(
                    username=username,
                    file_count=len(file_list),
                    matched_files=matched_files,
                    unmatched_locals=unmatched_locals,
                    overall_score=overall,
                    accepted=accepted,
                )
            )

    album_matches.sort(key=lambda m: m.overall_score, reverse=True)

    return AlbumMatchResult(album=album, matches=album_matches)


def _candidate_from_file(
    username: str, file_data: dict[str, Any]
) -> SearchCandidate | None:
    """
    _candidate_from_file: converte um arquivo remoto em SearchCandidate.

    input:
        username, dono do arquivo.
        file_data, dicionário com metadados do arquivo remoto.

    output:
        SearchCandidate ou None quando dados insuficientes.
    """
    filename = file_data.get("filename") or file_data.get("Filename")
    size = file_data.get("size") or file_data.get("Size")

    if not isinstance(filename, str) or not isinstance(size, int):
        return None

    title = file_data.get("title") or file_data.get("Title")

    if not isinstance(title, str):
        title = Path(filename).stem

    return SearchCandidate(
        username=username,
        filename=filename,
        size=size,
        title=title,
        artist=file_data.get("artist") or file_data.get("Artist"),
        album=file_data.get("album") or file_data.get("Album"),
        duration_seconds=file_data.get("duration") or file_data.get("Length"),
        bitrate_kbps=file_data.get("bitrate") or file_data.get("Bitrate"),
        format=Path(filename).suffix.removeprefix(".").lower(),
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
