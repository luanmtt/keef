import argparse
import json
import os
import time
from pathlib import Path

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.prompt import Confirm
from rich.table import Table

from keef.config import SlskdConfig
from keef.batch import load_metadata_report, preview_batch
from keef.library import scan_library
from keef.matching import candidates_from_responses, score_candidate
from keef.models import BatchPreviewItem, ConnectionReport, QualityPolicy, SearchRequest
from keef.music import try_read_audio
from keef.outputs import create_output_dir, write_metadata_report
from keef.rename import RenameEntry, plan_renames
from keef.slskd import SlskdClient

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

console = Console()


def _format_search_text(
    title: str | None, album: str | None, artist: str | None
) -> str:
    """
    _format_search_text: monta texto de pesquisa no formato título - álbum, artista.

    input:
        title, nome da faixa.
        album, nome do álbum.
        artist, nome do artista.

    output:
        str, texto formatado para pesquisa no Soulseek.
    """
    parts = []

    if title:
        parts.append(title)

    if album:
        parts.append(f" - {album}")

    if artist:
        parts.append(f", {artist}")

    return "".join(parts)


def _search_queries(
    title: str | None, album: str | None, artist: str | None
) -> list[tuple[str, str]]:
    """
    _search_queries: gera variações da query por fallback com sobrescrita.

    input:
        title, nome da faixa.
        album, nome do álbum.
        artist, nome do artista.

    output:
        list[tuple[str, str]], (query, parte_removida) ordenadas da mais
        específica para a mais genética.
    """
    queries: list[tuple[str, str]] = []

    if title and album and artist:
        queries.append((f"{title} - {album}, {artist}", ""))
        queries.append((f"{title} - {album}", artist))
        queries.append((title, f"{album}, {artist}"))
    elif title and album:
        queries.append((f"{title} - {album}", ""))
        queries.append((title, album))
    elif title and artist:
        queries.append((f"{title}, {artist}", ""))
        queries.append((title, artist))
    elif title:
        queries.append((title, ""))

    return queries


def _build_parser() -> argparse.ArgumentParser:
    """
    _build_parser: cria o parser da CLI.

    input:
        nenhum.

    output:
        argparse.ArgumentParser, parser configurado.
    """
    parser = argparse.ArgumentParser(
        prog="keef",
        description="keef — atualização segura de bibliotecas musicais via Soulseek",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser(
        "status",
        help="verifica conexão com slskd e Soulseek",
    )
    status_parser.add_argument("--url", help="URL base da API do slskd")
    status_parser.add_argument("--timeout", type=float, help="timeout em segundos")

    install_parser = subparsers.add_parser(
        "install",
        help="executa downloads a partir de um plano batch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplo:\n"
            "  keef install --plan outputs/07-15-18/plan.json\n"
            "  keef install --plan plan.json --execute\n"
            "  keef install --plan plan.json --execute --staging-dir ~/staging"
        ),
    )
    install_parser.add_argument(
        "--plan", type=Path, help="caminho para plan.json gerado pelo preview"
    )
    install_parser.add_argument(
        "--staging-dir",
        type=Path,
        default=Path("keef"),
        help="pasta de staging dentro do slskd (relativa ao diretório de downloads)",
    )
    install_parser.add_argument(
        "--execute",
        action="store_true",
        help="confirma e solicita o download; sem esta opção apenas simula",
    )
    install_parser.add_argument("--url", help="URL base da API do slskd")
    install_parser.add_argument("--timeout", type=float, help="timeout em segundos")

    scan_parser = subparsers.add_parser(
        "scan",
        help="lê metadados de áudio de um diretório",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplo:\n"
            "  keef scan ~/Music\n"
            "  keef scan songs --output-dir outputs"
        ),
    )
    scan_parser.add_argument("directory", type=Path, help="diretório da biblioteca")
    scan_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "diretório de relatórios com subpasta temporal; "
            "por padrão grava metadata.json na própria pasta escaneada"
        ),
    )

    preview_parser = subparsers.add_parser(
        "preview",
        help="pesquisa candidatos e gera plano de instalação",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplo:\n"
            "  keef preview outputs/07-15-18/metadata.json --online --verbose\n"
            "  keef preview metadata.json --online --policy higher --search-timeout 15\n"
            "  keef preview metadata.json --online -o plan.json"
        ),
    )
    preview_parser.add_argument("report", type=Path, help="caminho para metadata.json")
    preview_parser.add_argument(
        "--policy",
        choices=[policy.value for policy in QualityPolicy],
        default=QualityPolicy.HIGHER.value,
        help="política de bitrate: higher (default), lower, exact",
    )
    preview_parser.add_argument(
        "--target-kbps", type=int, help="bitrate alvo para --policy exact"
    )
    preview_parser.add_argument(
        "--search-timeout",
        type=int,
        default=5,
        help="timeout de cada pesquisa no slskd (segundos, default: 5)",
    )
    preview_parser.add_argument(
        "--search-delay",
        type=float,
        default=1.0,
        help="pausa entre pesquisas no slskd (segundos, default: 1.0)",
    )
    preview_parser.add_argument(
        "--online",
        action="store_true",
        help="pesquisa candidatos no slskd; sem isto o preview é offline",
    )
    preview_parser.add_argument(
        "--output", "-o", type=Path, help="caminho para salvar plan.json"
    )
    preview_parser.add_argument(
        "--verbose",
        action="store_true",
        help="exibe queries, respostas e fallback em tempo real",
    )
    preview_parser.add_argument("--url", help="URL base da API do slskd")
    preview_parser.add_argument("--timeout", type=float, help="timeout em segundos")

    rename_parser = subparsers.add_parser(
        "rename",
        help="renomeia downloads para o formato padrão de biblioteca",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplo:\n"
            "  keef rename downloads/keef\n"
            "  keef rename downloads/keef --dry\n"
            "  keef rename staging --execute"
        ),
    )
    rename_parser.add_argument("directory", type=Path, help="diretório com os downloads")
    rename_parser.add_argument(
        "--dry",
        action="store_true",
        help="apenas mostra as renomeações sem aplicar",
    )

    return parser


def _status_config(args: argparse.Namespace) -> SlskdConfig:
    """
    _status_config: monta a configuração do comando status.

    input:
        args, argumentos da CLI.

    output:
        SlskdConfig, configuração validada.
    """
    config_values = {}

    if args.url is not None:
        config_values["base_url"] = args.url

    if args.timeout is not None:
        config_values["timeout_seconds"] = args.timeout

    return SlskdConfig.from_sources(
        url=config_values.get("base_url"),
        token=os.getenv("KEEF_SLSKD_TOKEN"),
        timeout=config_values.get("timeout_seconds"),
        persist_url=args.url is not None,
    )


def _render_status(report: ConnectionReport) -> None:
    """
    _render_status: renderiza o relatório com Rich.

    input:
        report, relatório de conexão.

    output:
        None, imprime uma tabela no console.
    """
    table = Table(title="Estado do slskd")
    table.add_column("Indicador")
    table.add_column("Valor")

    values = report.model_dump()

    for key, value in values.items():
        table.add_row(key, str(value) if value is not None else "desconhecido")

    console.print(table)


def _run_status(args: argparse.Namespace) -> int:
    """
    _run_status: executa o comando status.

    input:
        args, argumentos da CLI.

    output:
        int, código de saída do comando.
    """
    try:
        config = _status_config(args)
    except ValueError as error:
        console.print(f"[red]Configuração inválida:[/red] {error}")
        return 2

    client = SlskdClient(config)

    try:
        report = client.get_status()
    finally:
        client.close()

    _render_status(report)

    return 0 if report.reachable and report.authenticated else 1


def _render_track(track) -> None:
    """
    _render_track: apresenta metadados da música.

    input:
        track, metadados de uma música local.

    output:
        None, imprime um painel Rich no console.
    """
    values = [
        f"Artista: {track.artist or 'ausente'}",
        f"Título: {track.title or 'ausente'}",
        f"Álbum: {track.album or 'ausente'}",
        f"Faixa: {track.track_number or 'ausente'}",
        f"Duração: {track.duration_seconds or 'ausente'} s",
        f"Bitrate: {track.bitrate_kbps or 'ausente'} kbps",
        f"Formato: {track.format}",
    ]
    console.print(Panel("\n".join(values), title="Música local"))


def _render_candidates(results) -> None:
    """
    _render_candidates: apresenta candidatos e scores.

    input:
        results, resultados de matching ordenados por score.

    output:
        None, imprime tabela Rich no console.
    """
    table = Table(title="Candidatos")
    table.add_column("#")
    table.add_column("Usuário")
    table.add_column("Arquivo")
    table.add_column("Score")
    table.add_column("Decisão")

    for index, result in enumerate(results, start=1):
        decision = "aceito" if result.accepted else "revisar"
        table.add_row(
            str(index),
            result.candidate.username,
            result.candidate.filename,
            f"{result.score:.2f}",
            decision,
        )

    console.print(table)


def _install_config(args: argparse.Namespace) -> SlskdConfig:
    """
    _install_config: monta configuração para instalação.

    input:
        args, argumentos do comando install.

    output:
        SlskdConfig, configuração validada para o cliente.
    """
    return SlskdConfig.from_sources(
        url=args.url,
        token=os.getenv("KEEF_SLSKD_TOKEN"),
        timeout=args.timeout,
        persist_url=args.url is not None,
    )


def _format_download_error(error: Exception) -> str:
    """
    _format_download_error: converte erro de download em mensagem legível.

    input:
        error, exceção capturada ao enfileirar um download.

    output:
        str, mensagem com diagnóstico de timeout, HTTP ou de rede.
    """
    if isinstance(error, httpx.TimeoutException):
        return (
            "o slskd demorou para responder — peer offline, lento "
            "ou fora da rede"
        )

    if isinstance(error, httpx.HTTPStatusError):
        response = error.response

        try:
            payload = response.json()
        except (ValueError, TypeError):
            payload = None

        if isinstance(payload, dict):
            message = payload.get("message") or payload.get("error")

            if isinstance(message, str) and message:
                return f"slskd recusou ({response.status_code}): {message}"

        return f"slskd respondeu HTTP {response.status_code}"

    return str(error) or error.__class__.__name__


def _human_size(bytes_val: int | float) -> str:
    """
    _human_size: formata bytes em unidades legíveis.

    input:
        bytes_val, tamanho em bytes.

    output:
        str, tamanho formatado (ex: 1.5 GB).
    """
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024

    return f"{bytes_val:.1f} TB"


def _human_rate(bytes_per_sec: float) -> str:
    """
    _human_rate: formata taxa de transferência.

    input:
        bytes_per_sec, velocidade em bytes/segundo.

    output:
        str, taxa formatada (ex: 2.5 MB/s).
    """
    if bytes_per_sec <= 0:
        return "---"

    return _human_size(int(bytes_per_sec)) + "/s"


def _human_elapsed(seconds: float) -> str:
    """
    _human_elapsed: formata tempo decorrido.

    input:
        seconds, segundos decorridos.

    output:
        str, tempo formatado (ex: 01:23).
    """
    minutes = int(seconds) // 60
    secs = int(seconds) % 60

    return f"{minutes:02d}:{secs:02d}"


def _extract_plan_entries(plan: dict) -> list[dict]:
    """
    _extract_plan_entries: extrai entradas de download do plano.

    input:
        plan, conteúdo do plan.json.

    output:
        list[dict], entradas normalizadas com username, filename, size, local_path.
    """
    entries = []

    for track in plan.get("tracks", []):
        entries.append(
            {
                "username": track["username"],
                "filename": track["filename"],
                "size": track.get("size", 0),
                "local_path": track["local_path"],
            }
        )

    for album_name, album_data in plan.get("albums", {}).items():
        best_users = plan.get("best_users", {}).get(album_name, [])

        if best_users:
            best_username = best_users[0]["username"]
            files = album_data["users"].get(best_username, [])
        else:
            all_files = []

            for username, user_files in album_data["users"].items():
                all_files.extend(user_files)

            files = all_files

        for f in files:
            entries.append(
                {
                    "username": f.get("username", ""),
                    "filename": f.get("filename", ""),
                    "size": f.get("size", 0),
                    "local_path": f.get("local_path", ""),
                }
            )

    return entries


def _run_install(args: argparse.Namespace) -> int:
    """
    _run_install: executa downloads a partir de um plano batch.

    input:
        args, argumentos do comando install.

    output:
        int, código de saída do install.
    """
    if args.plan is None:
        console.print("[red]Especifique --plan com o caminho para plan.json[/red]")
        return 2

    try:
        plan = json.loads(args.plan.read_text())
    except (OSError, ValueError) as error:
        console.print(f"[red]Erro ao ler plano:[/red] {error}")
        return 2

    entries = _extract_plan_entries(plan)

    if not entries:
        console.print("[yellow]Nenhuma entrada no plano.[/yellow]")
        return 1

    console.print(f"[cyan]Total de arquivos:[/cyan] {len(entries)}")

    if not args.execute:
        for entry in entries[:10]:
            console.print(
                f"  {entry['local_path']}: "
                f"{entry['username']} → {_human_size(entry['size'])}"
            )

        if len(entries) > 10:
            console.print(f"  ... e mais {len(entries) - 10} arquivos")

        console.print(
            "\n[yellow]Dry-run:[/yellow] use --execute para iniciar downloads."
        )
        return 0

    try:
        config = SlskdConfig.from_sources(
            url=args.url,
            token=os.getenv("KEEF_SLSKD_TOKEN"),
            timeout=args.timeout,
            persist_url=args.url is not None,
        )
    except ValueError as error:
        console.print(f"[red]Configuração inválida:[/red] {error}")
        return 2

    client = SlskdClient(config)
    start_time = time.monotonic()
    downloaded_bytes = 0
    completed_files = 0
    failed_files = 0

    try:
        with Progress(console=console) as progress:
            main_task = progress.add_task(
                "Instalando", total=len(entries), completed=0
            )
            size_task = progress.add_task(
                "Transferido", total=None, completed=0
            )

            for entry in entries:
                username = entry["username"]
                filename = entry["filename"]
                size = entry["size"]

                if not username or not filename:
                    failed_files += 1
                    progress.advance(main_task, 1)
                    continue

                try:
                    response = client.enqueue_download(
                        username=username,
                        filename=filename,
                        size=size,
                        destination=str(args.staging_dir),
                    )

                    downloaded_bytes += size
                    completed_files += 1

                    elapsed = time.monotonic() - start_time
                    rate = downloaded_bytes / elapsed if elapsed > 0 else 0

                    progress.update(size_task, completed=downloaded_bytes)
                    progress.advance(main_task, 1)

                    progress.update(
                        main_task,
                        description=(
                            f"[cyan]Instalando[/cyan] "
                            f"{completed_files}/{len(entries)} | "
                            f"{_human_elapsed(elapsed)} | "
                            f"{_human_rate(rate)} | "
                            f"{_human_size(downloaded_bytes)}"
                        ),
                    )

                except (httpx.HTTPError, OSError, TypeError, ValueError) as error:
                    failed_files += 1
                    progress.advance(main_task, 1)
                    console.print(
                        f"\n[red]Falha:[/red] {filename}: "
                        f"{_format_download_error(error)}"
                    )

    finally:
        client.close()

    elapsed = time.monotonic() - start_time
    rate = downloaded_bytes / elapsed if elapsed > 0 else 0

    console.print(
        f"\n[green]Concluído:[/green] {completed_files}/{len(entries)} arquivos "
        f"({_human_size(downloaded_bytes)}) em {_human_elapsed(elapsed)} "
        f"({_human_rate(rate)})"
    )

    if failed_files > 0:
        console.print(f"[red]Falhas:[/red] {failed_files} arquivos")

    return 0 if failed_files == 0 else 1
    """
    _run_install: executa o fluxo single-track seguro.

    input:
        args, argumentos do comando install.

    output:
        int, código de saída do fluxo.
    """
    track = try_read_audio(args.path)

    if isinstance(track, str):
        console.print(f"[red]{track}[/red]")
        return 2

    _render_track(track)

    try:
        config = _install_config(args)
    except ValueError as error:
        console.print(f"[red]Configuração inválida:[/red] {error}")
        return 2

    search_text = " ".join(value for value in [track.artist, track.title] if value)
    client = SlskdClient(config)

    try:
        search = client.search(SearchRequest(search_text=search_text))
        responses = search.responses or client.get_search_responses(search.id)
    except (httpx.HTTPError, ValueError, TypeError, OSError) as error:
        console.print(f"[red]Falha na pesquisa:[/red] {error}")
        return 1
    finally:
        client.close()

    candidates = candidates_from_responses(responses)

    if not candidates:
        console.print("[yellow]Nenhum candidato encontrado.[/yellow]")
        return 1

    results = [score_candidate(track, candidate) for candidate in candidates]
    results.sort(key=lambda result: result.score, reverse=True)
    _render_candidates(results)
    selected = results[0]

    if not selected.accepted:
        console.print("[yellow]O melhor candidato exige revisão manual.[/yellow]")
        return 1

    if not args.execute:
        console.print(
            f"[cyan]Dry-run:[/cyan] {selected.candidate.filename} "
            f"seria salvo em {args.staging_dir}."
        )
        return 0

    if args.staging_dir.resolve().is_relative_to(args.path.resolve().parent):
        console.print("[red]A pasta de staging não pode ficar na biblioteca original.[/red]")
        return 2

    if not Confirm.ask("Confirmar solicitação de download?", default=False):
        console.print("[yellow]Download cancelado.[/yellow]")
        return 0

    client = SlskdClient(config)

    try:
        response = client.enqueue_download(
            username=selected.candidate.username,
            filename=selected.candidate.filename,
            size=selected.candidate.size,
            destination=str(args.staging_dir),
        )
    except (httpx.HTTPError, ValueError, TypeError, OSError) as error:
        console.print(f"[red]Falha ao solicitar download:[/red] {error}")
        return 1
    finally:
        client.close()

    _render_download_status(response)
    return 0


def _render_download_status(response: dict) -> None:
    """
    _render_download_status: apresenta resposta de enfileiramento.

    input:
        response, payload retornado pelo slskd.

    output:
        None, imprime identificador e estado disponíveis.
    """
    identifier = response.get("id") or response.get("batchId") or response.get("batch_id")
    state = response.get("state") or response.get("status") or "queued"

    console.print(
        "[green]Download solicitado.[/green] "
        f"id={identifier or 'indisponível'} state={state}"
    )


def _render_scan_summary(result, report_path: Path) -> None:
    """
    _render_scan_summary: apresenta resumo do parsing.

    input:
        result, resultado do scan da biblioteca.
        report_path, caminho do relatório JSON.

    output:
        None, imprime resumo Rich no console.
    """
    album_count = sum(1 for t in result.tracks if _is_album_track(t.path))
    track_count = len(result.tracks) - album_count

    console.print(
        f"[green]Tracks individuais:[/green] {track_count}\n"
        f"[green]💿 Tracks em álbuns:[/green] {album_count}\n"
        f"[yellow]Erros:[/yellow] {len(result.errors)}\n"
        f"[cyan]Relatório:[/cyan] {report_path}"
    )


def _run_scan(args: argparse.Namespace) -> int:
    """
    _run_scan: executa parsing recursivo sem downloads.

    input:
        args, diretório e opções do comando scan.

    output:
        int, código de saída do parsing.
    """
    try:
        result = scan_library(args.directory)
    except NotADirectoryError as error:
        console.print(f"[red]{error}[/red]")
        return 2

    if args.output_dir is None:
        report_path = write_metadata_report(
            args.directory, result.tracks, result.errors
        )
    else:
        output_dir = create_output_dir(args.output_dir)
        report_path = write_metadata_report(output_dir, result.tracks, result.errors)

    _render_scan_summary(result, report_path)

    if not result.tracks:
        return 1

    return 0


def _render_preview(items) -> None:
    """
    _render_preview: apresenta decisões do preview batch.

    input:
        items, resultados individuais do preview.

    output:
        None, imprime resumo por faixa com melhores resultados.
    """
    for item in items:
        if item.error:
            console.print(
                f"[red]{_track_label(item.track)}: erro — {item.error}[/red]"
            )
            console.print()
            continue

        accepted = [
            (match, quality)
            for match, quality in zip(item.candidates, item.quality_decisions)
            if match.accepted and quality.eligible
        ]

        if not accepted:
            continue

        count = len(item.candidates)
        console.print(
            f"[bold]{_track_label(item.track)}[/bold] obteve "
            f"[yellow]{count}[/yellow] resultado"
            f"{'s' if count != 1 else ''}."
        )
        console.print("|")
        console.print("|")

        console.print("[dim]- melhores resultados:[/dim]")

        for match, quality in accepted[:5]:
            console.print(
                f"  [green]{match.candidate.username}[/green] "
                f"[cyan]{match.candidate.filename}[/cyan]"
            )

        if len(accepted) > 5:
            console.print(
                f"  [dim]... e mais {len(accepted) - 5} aceitos[/dim]"
            )

        console.print()


def _print_separator() -> None:
    """
    _print_separator: imprime uma barra separadora.
    """
    console.print("━" * 50)


def _print_preview_header(online: bool) -> None:
    """
    _print_preview_header: imprime cabeçalho com modo do preview.

    input:
        online, True quando o preview pesquisa no slskd.

    output:
        None, imprime barra e linha do processo.
    """
    option = "--online" if online else "--offline"
    console.print()
    _print_separator()
    console.print(f"keef: preview ([italic]{option}[/italic])")


def _track_label(track) -> str:
    """
    _track_label: monta rótulo exibível de uma faixa.

    input:
        track, metadados da música.

    output:
        str, título ou caminho como rótulo do preview.
    """
    if track.title and track.artist:
        return f"{track.title} — {track.artist}"

    return track.title or track.path


def _is_album_track(track_path: str) -> bool:
    """
    _is_album_track: verifica se a track pertence a uma pasta de álbum.

    input:
        track_path, caminho relativo da track.

    output:
        bool, True se o caminho contiver um diretório pai (pasta de álbum).
    """
    return Path(track_path).parent != Path(".")


def _album_key(track) -> str:
    """
    _album_key: extrai chave de agrupamento do álbum.

    input:
        track, metadados da música.

    output:
        str, chave no formato 'artist - album' ou pasta do caminho.
    """
    if track.artist and track.album:
        return f"{track.artist} - {track.album}"

    parent = str(Path(track.path).parent)

    return parent if parent != "." else track.path


def _analyze_album_results(
    items: list[BatchPreviewItem],
) -> dict[str, list[dict]]:
    """
    _analyze_album_results: agrupa resultados por álbum e usuário.

    input:
        items, resultados do preview batch.

    output:
        dict, chave=álbum, valor=lista de {username, tracks_aceitas, total}.
    """
    albums: dict[str, dict[str, list]] = {}

    for item in items:
        if item.error or not _is_album_track(item.track.path):
            continue

        key = _album_key(item.track)
        albums.setdefault(key, {})

        for match, quality in zip(item.candidates, item.quality_decisions):
            if match.accepted and quality.eligible:
                username = match.candidate.username
                albums[key].setdefault(username, []).append(
                    {
                        "local_path": item.track.path,
                        "remote_filename": match.candidate.filename,
                        "remote_size": match.candidate.size,
                        "score": match.score,
                    }
                )
                break

    result = {}

    for album_name, users in albums.items():
        total_tracks = sum(
            1 for item in items
            if _is_album_track(item.track.path) and _album_key(item.track) == album_name
        )

        user_list = []

        for username, matched_files in users.items():
            count = len(matched_files)

            if count >= total_tracks * 0.5:
                user_list.append(
                    {
                        "username": username,
                        "matched_count": count,
                        "total_tracks": total_tracks,
                        "coverage": round(count / total_tracks, 2),
                        "files": matched_files,
                    }
                )

        user_list.sort(key=lambda u: u["coverage"], reverse=True)

        if user_list:
            result[album_name] = user_list

    return result


def _save_batch_plan(path: Path, items: list[BatchPreviewItem]) -> bool:
    """
    _save_batch_plan: persiste candidatos aceitos para instalação futura.

    input:
        path, caminho do arquivo JSON de saída.
        items, resultados do preview batch.

    output:
        bool, True quando o plano contém candidatos e foi escrito.
    """
    plan = {"tracks": [], "albums": {}}

    for item in items:
        if item.error:
            continue

        is_album = _is_album_track(item.track.path)

        for match, quality in zip(item.candidates, item.quality_decisions):
            if match.accepted and quality.eligible:
                entry = {
                    "local_path": item.track.path,
                    "username": match.candidate.username,
                    "filename": match.candidate.filename,
                    "size": match.candidate.size,
                    "score": match.score,
                }

                if is_album:
                    key = _album_key(item.track)
                    plan["albums"].setdefault(key, {"users": {}, "total_tracks": 0})
                    plan["albums"][key]["users"].setdefault(
                        match.candidate.username, []
                    ).append(entry)
                    plan["albums"][key]["total_tracks"] = sum(
                        1 for i in items
                        if _is_album_track(i.track.path) and _album_key(i.track) == key
                    )
                else:
                    plan["tracks"].append(entry)

                break

    best_users = {}

    for album_name, album_data in plan["albums"].items():
        total = album_data["total_tracks"]
        ranked = []

        for username, files in album_data["users"].items():
            count = len(files)
            coverage = round(count / total, 2) if total > 0 else 0

            if count >= total * 0.5:
                ranked.append(
                    {
                        "username": username,
                        "matched_count": count,
                        "total_tracks": total,
                        "coverage": coverage,
                    }
                )

        ranked.sort(key=lambda u: u["coverage"], reverse=True)

        if ranked:
            best_users[album_name] = ranked

    plan["best_users"] = best_users

    has_tracks = bool(plan["tracks"])
    has_albums = any(files for files in plan["albums"].values() if files.get("users"))

    if not has_tracks and not has_albums:
        return False

    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))

    return True


def _render_album_summary(items: list[BatchPreviewItem]) -> None:
    """
    _render_album_summary: mostra resumo de álbuns com fontes recomendadas.

    input:
        items, resultados do preview batch.

    output:
        None, imprime resumo de álbuns com melhor usuário.
    """
    albums: dict[str, dict[str, list]] = {}
    album_totals: dict[str, int] = {}

    for item in items:
        if item.error or not _is_album_track(item.track.path):
            continue

        key = _album_key(item.track)
        album_totals[key] = album_totals.get(key, 0) + 1

        for match, quality in zip(item.candidates, item.quality_decisions):
            if match.accepted and quality.eligible:
                albums.setdefault(key, {}).setdefault(
                    match.candidate.username, []
                ).append(item.track.path)
                break

    if not albums:
        return

    console.print()

    for album_name, users in albums.items():
        total = album_totals.get(album_name, 0)

        if total == 0:
            continue

        ranked = []

        for username, matched_paths in users.items():
            count = len(matched_paths)
            coverage = count / total

            if coverage >= 0.5:
                ranked.append((username, count, coverage))

        ranked.sort(key=lambda x: x[2], reverse=True)

        if ranked:
            best_user, best_count, best_coverage = ranked[0]
            pct = int(best_coverage * 100)
            console.print(
                f"💿 [bold]{album_name}[/bold]: [green]{best_user}[/green] "
                f"tem [yellow]{best_count}/{total}[/yellow] faixas "
                f"({pct}%) — fonte recomendada"
            )
        else:
            best_count = max(len(p) for p in users.values()) if users else 0
            console.print(
                f"💿 [bold]{album_name}[/bold]: melhor fonte tem "
                f"[yellow]{best_count}/{total}[/yellow] faixas (<50%)"
            )


def _render_missing_summary(items) -> None:
    """
    _render_missing_summary: mostra faixas sem candidato aceito.

    input:
        items, resultados individuais do preview.

    output:
        None, imprime bloco final com faixas não encontradas.
    """
    missing = []

    for item in items:
        if item.error:
            missing.append((_track_label(item.track), f"erro: {item.error}"))
            continue

        accepted = any(
            match.accepted and quality.eligible
            for match, quality in zip(item.candidates, item.quality_decisions)
        )

        if not accepted:
            missing.append((_track_label(item.track), None))

    if not missing:
        console.print("\n[green]Todas as faixas foram encontradas.[/green]")
        return

    console.print("\n[red]Não encontradas:[/red] " f"[bold]{len(missing)}[/bold]")

    for label, detail in missing:
        if detail:
            console.print(f"  • [bold]{label}[/bold] [dim]({detail})[/dim]")
        else:
            console.print(f"  • [bold]{label}[/bold]")


def _run_preview(args: argparse.Namespace) -> int:
    """
    _run_preview: executa preview batch offline ou online.

    input:
        args, relatório, política e opções da CLI.

    output:
        int, código de saída do preview.
    """
    try:
        report = load_metadata_report(args.report)
    except (OSError, ValueError) as error:
        console.print(f"[red]Relatório inválido:[/red] {error}")
        return 2

    _print_preview_header(args.online)

    client = None

    if args.online:
        try:
            client = SlskdClient(
                SlskdConfig.from_sources(
                    url=args.url,
                    token=os.getenv("KEEF_SLSKD_TOKEN"),
                    timeout=args.timeout,
                    persist_url=args.url is not None,
                )
            )
        except ValueError as error:
            console.print(f"[red]Configuração inválida:[/red] {error}")
            return 2

    def candidate_provider(track, progress=None, task_id=None) -> list:
        """
        candidate_provider: pesquisa candidatos para uma track.

        input:
            track, música que será pesquisada.
            progress, instância do Rich Progress opcional.
            task_id, identificador da tarefa de progresso.

        output:
            list, candidatos normalizados ou lista vazia no modo offline.
        """
        if client is None:
            if progress is not None:
                progress.advance(task_id, 1)

            return []

        queries = _search_queries(track.title, track.album, track.artist)
        responses: list = []

        for query, removed in queries:
            if args.verbose:
                if removed:
                    console.print(
                        f"\n[dim]Query:[/dim] [cyan]{query}[/cyan] "
                        f"[red](-{removed})[/red]"
                    )
                else:
                    console.print(f"\n[dim]Query:[/dim] [cyan]{query}[/cyan]")

            search = client.search(
                SearchRequest(search_text=query, search_timeout=args.search_timeout)
            )
            responses = search.responses or client.wait_for_search_responses(
                search.id, max_wait_seconds=args.search_timeout
            )

            if args.verbose:
                label = "💿 " + track.path if _is_album_track(track.path) else track.path
                console.print(
                    f"[dim]Respostas para[/dim] [green]{label}[/green][dim]:[/dim] "
                    f"[yellow]{len(responses)}[/yellow]"
                )

            if responses:
                break

        if progress is not None:
            progress.advance(task_id, 1)

        return candidates_from_responses(responses)

    try:
        if args.online and report.tracks:
            with Progress(console=console) as progress:
                task = progress.add_task("Pesquisando", total=len(report.tracks))

                items = preview_batch(
                    report,
                    lambda track: candidate_provider(track, progress, task),
                    QualityPolicy(args.policy),
                    args.target_kbps,
                    search_delay_seconds=args.search_delay,
                )
        else:
            items = preview_batch(
                report,
                candidate_provider,
                QualityPolicy(args.policy),
                args.target_kbps,
                search_delay_seconds=args.search_delay,
            )
    finally:
        if client is not None:
            client.close()

    _print_separator()
    _render_preview(items)
    _render_album_summary(items)
    _render_missing_summary(items)

    plan_path = args.output if args.output is not None else args.report.parent / "plan.json"
    saved = _save_batch_plan(plan_path, items)

    if saved:
        console.print(f"[cyan]Plano salvo em:[/cyan] {plan_path}")
    else:
        console.print(
            "[yellow]Nenhum candidato aceito — plan.json não foi criado.[/yellow]"
        )

    return 0


def _run_rename(args: argparse.Namespace) -> int:
    """
    _run_rename: renomeia downloads para o formato padrão de biblioteca.

    input:
        args, diretório e opção de dry-run.

    output:
        int, código de saída do rename.
    """
    if not args.directory.exists():
        console.print(f"[red]Diretório não encontrado:[/red] {args.directory}")
        return 2

    if not args.directory.is_dir():
        console.print(f"[red]Não é um diretório:[/red] {args.directory}")
        return 2

    entries = plan_renames(args.directory)
    pending: list[tuple[str, str]] = []
    unchanged: list[RenameEntry] = []

    for entry in entries:
        destination = entry["destination"]

        if destination is None or destination == entry["source"]:
            unchanged.append(entry)
        else:
            pending.append((entry["source"], destination))

    for entry in unchanged:
        if entry["destination"] is None:
            console.print(
                f"[yellow]Ignorado:[/yellow] {Path(entry['source']).name} — "
                f"{entry['reason']}"
            )

    if not pending:
        console.print("[yellow]Nenhum arquivo para renomear.[/yellow]")
        return 0

    console.print(f"[cyan]Renomeações:[/cyan] {len(pending)}")

    for source_path, destination_path in pending:
        console.print(
            f"  {Path(source_path).name} → [green]{Path(destination_path).name}[/green]"
        )

    if args.dry:
        console.print("\n[yellow]Dry-run:[/yellow] use sem --dry para aplicar.")
        return 0

    applied = 0

    for source_path, destination_path in pending:
        try:
            Path(source_path).rename(destination_path)
            applied += 1
        except OSError as error:
            console.print(
                f"[red]Falha ao renomear:[/red] {source_path}: {error}"
            )
            return 1

    console.print(f"[green]Renomeados:[/green] {applied} arquivos.")

    return 0


def main() -> int:
    """
    main: executa a CLI.

    input:
        argumentos do processo.

    output:
        int, código de saída da aplicação.
    """
    args = _build_parser().parse_args()

    if args.command == "status":
        return _run_status(args)

    if args.command == "install":
        return _run_install(args)

    if args.command == "scan":
        return _run_scan(args)

    if args.command == "preview":
        return _run_preview(args)

    if args.command == "rename":
        return _run_rename(args)

    return 2

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
