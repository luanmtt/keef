from argparse import Namespace
from io import StringIO
from pathlib import Path

from rich.console import Console

import keef
from keef.models import ConnectionReport
from keef.models import MusicTrack, SearchResult
from keef.library import LibraryScanResult

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


class FakeInstallClient(FakeClient):
    def __init__(self, report: ConnectionReport, search_result: SearchResult) -> None:
        """
        __init__: prepara cliente simulado para instalação.

        input:
            report, relatório fixo de conexão.
            search_result, resposta fixa de pesquisa.

        output:
            None, inicializa o dublê com pesquisa e registro de download.
        """
        super().__init__(report)
        self.search_result = search_result
        self.download_requested = False

    def search(self, request) -> SearchResult:
        """
        search: retorna pesquisa simulada.

        input:
            request, solicitação de pesquisa do keef.

        output:
            SearchResult, resultado fixo de pesquisa.
        """
        return self.search_result

    def get_search_responses(self, search_id) -> list[dict]:
        """
        get_search_responses: retorna respostas simuladas.

        input:
            search_id, identificador da pesquisa.

        output:
            list[dict], respostas incluídas na pesquisa.
        """
        return self.search_result.responses

    def enqueue_download(self, **kwargs) -> dict:
        """
        enqueue_download: registra uma solicitação simulada.

        input:
            kwargs, dados do candidato e destino do download.

        output:
            dict, confirmação simulada da fila.
        """
        self.download_requested = True
        return {"queued": True, "state": "queued", "id": "batch-1"}


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


def test_install_command_dry_run_does_not_request_download(monkeypatch, tmp_path) -> None:
    """
    test_install_command_dry_run_does_not_request_download: protege dry-run.

    input:
        música local e candidato remoto simulados.

    output:
        None, teste aprovado quando nenhuma solicitação é enviada.
    """
    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))
    track = MusicTrack(
        path=str(tmp_path / "blue.mp3"),
        title="Blue",
        artist="Artist",
        duration_seconds=210,
    )
    search_result = SearchResult.model_validate(
        {
            "id": "12345678-1234-5678-1234-567812345678",
            "responses": [
                {
                    "username": "alice",
                    "files": [
                        {
                            "filename": "Artist - Blue.mp3",
                            "size": 1_000,
                            "title": "Blue",
                            "artist": "Artist",
                            "duration": 210,
                        }
                    ],
                }
            ],
        }
    )
    fake_client = FakeInstallClient(
        ConnectionReport(reachable=True, authenticated=True),
        search_result,
    )
    def read_track(path: Path) -> MusicTrack:
        """
        read_track: retorna a música simulada.

        input:
            path, caminho recebido pelo parser.

        output:
            MusicTrack, metadados fixos do teste.
        """
        return track

    def build_install_client(config) -> FakeInstallClient:
        """
        build_install_client: retorna cliente simulado.

        input:
            config, configuração recebida pela CLI.

        output:
            FakeInstallClient, cliente controlado pelo teste.
        """
        return fake_client

    monkeypatch.setattr(keef, "try_read_audio", read_track)
    monkeypatch.setattr(keef, "SlskdClient", build_install_client)

    exit_code = keef._run_install(
        Namespace(
            path=Path(track.path),
            staging_dir=tmp_path.parent / "staging",
            execute=False,
            url="http://localhost:5030",
            token=None,
            timeout=None,
        )
    )

    assert exit_code == 0
    assert fake_client.download_requested is False
    assert "Dry-run" in output.getvalue()


def test_install_command_requests_download_after_confirmation(monkeypatch, tmp_path) -> None:
    """
    test_install_command_requests_download_after_confirmation: verifica confirmação.

    input:
        música, candidato e confirmação simulados.

    output:
        None, teste aprovado quando download é solicitado.
    """
    track = MusicTrack(
        path=str(tmp_path / "blue.mp3"),
        title="Blue",
        artist="Artist",
        duration_seconds=210,
    )
    search_result = SearchResult.model_validate(
        {
            "id": "12345678-1234-5678-1234-567812345678",
            "responses": [
                {
                    "username": "alice",
                    "files": [
                        {
                            "filename": "Artist - Blue.mp3",
                            "size": 1_000,
                            "title": "Blue",
                            "artist": "Artist",
                            "duration": 210,
                        }
                    ],
                }
            ],
        }
    )
    fake_client = FakeInstallClient(
        ConnectionReport(reachable=True, authenticated=True),
        search_result,
    )
    def read_track(path: Path) -> MusicTrack:
        """
        read_track: retorna a música simulada.

        input:
            path, caminho recebido pelo parser.

        output:
            MusicTrack, metadados fixos do teste.
        """
        return track

    def build_install_client(config) -> FakeInstallClient:
        """
        build_install_client: retorna cliente simulado.

        input:
            config, configuração recebida pela CLI.

        output:
            FakeInstallClient, cliente controlado pelo teste.
        """
        return fake_client

    def confirm_download(prompt, default=False) -> bool:
        """
        confirm_download: aprova confirmação no teste.

        input:
            prompt, texto exibido ao usuário.
            default, valor padrão da confirmação.

        output:
            bool, sempre True para simular aprovação.
        """
        return True

    monkeypatch.setattr(keef, "try_read_audio", read_track)
    monkeypatch.setattr(keef, "SlskdClient", build_install_client)
    monkeypatch.setattr(keef.Confirm, "ask", confirm_download)

    exit_code = keef._run_install(
        Namespace(
            path=Path(track.path),
            staging_dir=tmp_path.parent / "staging",
            execute=True,
            url="http://localhost:5030",
            token=None,
            timeout=None,
        )
    )

    assert exit_code == 0
    assert fake_client.download_requested is True


def test_scan_command_writes_report(monkeypatch, tmp_path) -> None:
    """
    test_scan_command_writes_report: verifica comando de parsing.

    input:
        diretório e resultado de scan simulados.

    output:
        None, teste aprovado quando relatório é criado e código é zero.
    """
    track = MusicTrack(path=str(tmp_path / "blue.mp3"), title="Blue")
    scan_result = LibraryScanResult(tracks=[track])
    output_dir = tmp_path / "outputs" / "03" / "09-18-42"
    report_path = output_dir / "metadata.json"

    def fake_scan(directory: Path) -> LibraryScanResult:
        """
        fake_scan: retorna biblioteca simulada.

        input:
            directory, diretório recebido pela CLI.

        output:
            LibraryScanResult, resultado fixo do parsing.
        """
        return scan_result

    def fake_create_output_dir(root: Path) -> Path:
        """
        fake_create_output_dir: retorna saída temporal simulada.

        input:
            root, raiz de relatórios recebida pela CLI.

        output:
            Path, diretório de relatório do teste.
        """
        return output_dir

    def fake_write_report(directory, tracks, errors) -> Path:
        """
        fake_write_report: simula gravação do relatório.

        input:
            directory, tracks e errors do scan.

        output:
            Path, caminho do relatório simulado.
        """
        return report_path

    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))
    monkeypatch.setattr(keef, "scan_library", fake_scan)
    monkeypatch.setattr(keef, "create_output_dir", fake_create_output_dir)
    monkeypatch.setattr(keef, "write_metadata_report", fake_write_report)

    exit_code = keef._run_scan(
        Namespace(directory=tmp_path, output_dir=tmp_path / "outputs")
    )

    assert exit_code == 0
    assert "Tracks lidas: 1" in output.getvalue()
    assert "metadata.json" in output.getvalue()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
