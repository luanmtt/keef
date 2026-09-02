from argparse import Namespace
from io import StringIO

from rich.console import Console

import keef
from keef.models import ConnectionReport

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FakeClient:
    def __init__(self, report: ConnectionReport) -> None:
        """
        __init__: prepara cliente simulado.

        input:
            report, relatório fixo.

        output:
            None, inicializa o dublê HTTP.
        """
        self.report = report

    def get_status(self) -> ConnectionReport:
        """
        get_status: retorna relatório simulado.

        input:
            nenhum.

        output:
            ConnectionReport, estado configurado.
        """
        return self.report

    def close(self) -> None:
        """
        close: simula fechamento do cliente.

        input:
            nenhum.

        output:
            None.
        """
        return None


def test_status_command_uses_rich_output(monkeypatch) -> None:
    """
    test_status_command_uses_rich_output: verifica saída Rich.

    input:
        cliente slskd simulado.

    output:
        None, teste aprovado quando a tabela contém o status.
    """
    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))
    def client_factory(config):
        """
        client_factory: cria cliente simulado conectado.

        input:
            config, configuração recebida pela CLI.

        output:
            FakeClient, cliente com status conectado.
        """
        return FakeClient(
            ConnectionReport(
                reachable=True,
                authenticated=True,
                soulseek_connected=True,
                account="alice",
            )
        )

    monkeypatch.setattr(keef, "SlskdClient", client_factory)

    exit_code = keef._run_status(
        Namespace(
            url="http://localhost:5030",
            token=None,
            timeout=None,
        )
    )

    assert exit_code == 0
    assert "Estado do slskd" in output.getvalue()
    assert "alice" in output.getvalue()


def test_status_command_returns_failure_for_unreachable_service(monkeypatch) -> None:
    """
    test_status_command_returns_failure_for_unreachable_service: trata serviço offline.

    input:
        relatório de serviço indisponível.

    output:
        None, teste aprovado quando o código de saída é um.
    """
    def client_factory(config):
        """
        client_factory: cria cliente simulado offline.

        input:
            config, configuração recebida pela CLI.

        output:
            FakeClient, cliente com status indisponível.
        """
        return FakeClient(
            ConnectionReport(
                reachable=False,
                detail="serviço indisponível",
            )
        )

    monkeypatch.setattr(keef, "SlskdClient", client_factory)

    exit_code = keef._run_status(
        Namespace(
            url="http://localhost:5030",
            token=None,
            timeout=None,
        )
    )

    assert exit_code == 1

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
