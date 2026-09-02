import argparse
import os

from rich.console import Console
from rich.table import Table

from keef.config import SlskdConfig
from keef.models import ConnectionReport
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

    environment_values = {
        "base_url": os.getenv("KEEF_SLSKD_URL"),
        "api_token": os.getenv("KEEF_SLSKD_TOKEN"),
        "timeout_seconds": os.getenv("KEEF_SLSKD_TIMEOUT", "10"),
    }
    environment_values.update(config_values)

    return SlskdConfig.model_validate(environment_values)


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

    return 2

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
