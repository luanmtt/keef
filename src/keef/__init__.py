import argparse
from pathlib import Path

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

from keef.config import SlskdConfig
from keef.library import scan_library
from keef.matching import candidates_from_responses, score_candidate
from keef.models import ConnectionReport, SearchRequest
from keef.music import try_read_mp3
from keef.outputs import create_output_dir, write_metadata_report
from keef.slskd import SlskdClient

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

console = Console()


def _build_parser() -> argparse.ArgumentParser:
    """
    _build_parser: cria o parser da CLI.

    input:
        nenhum.

    output:
        argparse.ArgumentParser, parser configurado.
    """
    parser = argparse.ArgumentParser(prog="keef")
    subparsers = parser.add_subparsers(dest="command", required=True)
    status_parser = subparsers.add_parser("status", help="verifica o estado do slskd")
    status_parser.add_argument("--url", help="URL base da API do slskd")
    status_parser.add_argument("--token", help="token da API do slskd")
    status_parser.add_argument("--timeout", type=float, help="timeout em segundos")
    install_parser = subparsers.add_parser(
        "install", help="pesquisa e prepara uma música para instalação"
    )
    install_parser.add_argument("path", type=Path, help="caminho do MP3 local")
    install_parser.add_argument(
        "--staging-dir",
        type=Path,
        default=Path("keef-staging"),
        help="pasta de staging para o download",
    )
    install_parser.add_argument(
        "--execute",
        action="store_true",
        help="confirma e solicita o download; sem esta opção apenas simula",
    )
    install_parser.add_argument("--url", help="URL base da API do slskd")
    install_parser.add_argument("--token", help="token da API do slskd")
    install_parser.add_argument("--timeout", type=float, help="timeout em segundos")
    scan_parser = subparsers.add_parser(
        "scan", help="lê metadados MP3 de um diretório"
    )
    scan_parser.add_argument("directory", type=Path, help="diretório da biblioteca")
    scan_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="diretório raiz dos relatórios",
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

    if args.token is not None:
        config_values["api_token"] = args.token

    if args.timeout is not None:
        config_values["timeout_seconds"] = args.timeout

    return SlskdConfig.from_sources(
        url=config_values.get("base_url"),
        token=config_values.get("api_token"),
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
        token=args.token,
        timeout=args.timeout,
        persist_url=args.url is not None,
    )


def _run_install(args: argparse.Namespace) -> int:
    """
    _run_install: executa o fluxo single-track seguro.

    input:
        args, argumentos do comando install.

    output:
        int, código de saída do fluxo.
    """
    track = try_read_mp3(args.path)

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
        client.enqueue_download(
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

    console.print("[green]Download solicitado com sucesso.[/green]")
    return 0


def _render_scan_summary(result, report_path: Path) -> None:
    """
    _render_scan_summary: apresenta resumo do parsing.

    input:
        result, resultado do scan da biblioteca.
        report_path, caminho do relatório JSON.

    output:
        None, imprime resumo Rich no console.
    """
    console.print(
        f"[green]Tracks lidas:[/green] {len(result.tracks)}\n"
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

    output_dir = create_output_dir(args.output_dir)
    report_path = write_metadata_report(output_dir, result.tracks, result.errors)
    _render_scan_summary(result, report_path)

    if not result.tracks:
        return 1

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

    return 2

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
