import json
from argparse import Namespace
from io import StringIO
from pathlib import Path

from rich.console import Console

import keef
from keef.models import BatchPreviewItem
from keef.models import ConnectionReport
from keef.models import MatchResult, QualityDecision
from keef.models import MusicTrack, SearchCandidate, SearchResult
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


def test_install_command_dry_run_shows_plan_entries(monkeypatch, tmp_path) -> None:
    """
    test_install_command_dry_run_shows_plan_entries: protege dry-run.

    input:
        plan.json com uma entrada de track.

    output:
        None, teste aprovado quando dry-run mostra entradas sem baixar.
    """
    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({
        "tracks": [
            {
                "local_path": "blue.mp3",
                "username": "alice",
                "filename": "Artist - Blue.mp3",
                "size": 1_000_000,
                "score": 0.95,
            }
        ],
        "albums": {},
        "best_users": {},
    }))

    exit_code = keef._run_install(
        Namespace(
            plan=plan_path,
            staging_dir=tmp_path / "staging",
            execute=False,
            url="http://localhost:5030",
            timeout=None,
        )
    )

    assert exit_code == 0
    assert "Dry-run" in output.getvalue()
    assert "blue.mp3" in output.getvalue()


def test_install_command_execute_enqueues_downloads(monkeypatch, tmp_path) -> None:
    """
    test_install_command_execute_enqueues_downloads: verifica execução.

    input:
        plan.json com uma entrada e --execute.

    output:
        None, teste aprovado quando download é solicitado.
    """
    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps({
        "tracks": [
            {
                "local_path": "blue.mp3",
                "username": "alice",
                "filename": "Artist - Blue.mp3",
                "size": 1_000_000,
                "score": 0.95,
            }
        ],
        "albums": {},
        "best_users": {},
    }))

    download_requested = []

    def build_client(config):
        class FakeClient:
            def enqueue_download(self, **kwargs):
                download_requested.append(kwargs)
                return {"id": "batch-1", "state": "queued"}

            def close(self):
                pass

        return FakeClient()

    monkeypatch.setattr(keef, "SlskdClient", build_client)

    exit_code = keef._run_install(
        Namespace(
            plan=plan_path,
            staging_dir=tmp_path / "staging",
            execute=True,
            url="http://localhost:5030",
            timeout=None,
        )
    )

    assert exit_code == 0
    assert len(download_requested) == 1
    assert download_requested[0]["username"] == "alice"
    assert "Concluído" in output.getvalue()


def test_scan_command_writes_report(monkeypatch, tmp_path) -> None:
    """
    test_scan_command_writes_report: verifica comando de parsing.

    input:
        diretório e resultado de scan simulados.

    output:
        None, teste aprovado quando relatório é criado e código é zero.
    """
    track = MusicTrack(path="blue.mp3", title="Blue")
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
    assert "Tracks individuais: 1" in output.getvalue()
    assert "metadata.json" in output.getvalue()


def test_scan_command_defaults_to_scanned_directory(monkeypatch, tmp_path) -> None:
    """
    test_scan_command_defaults_to_scanned_directory: grava na pasta escaneada.

    input:
        diretório e resultado de scan simulados sem --output-dir.

    output:
        None, teste aprovado quando o relatório fica junto da biblioteca.
    """
    track = MusicTrack(path="blue.mp3", title="Blue")
    scan_result = LibraryScanResult(tracks=[track])
    report_path = tmp_path / "metadata.json"

    def fake_scan(directory: Path) -> LibraryScanResult:
        """
        fake_scan: retorna biblioteca simulada.

        input:
            directory, diretório recebido pela CLI.

        output:
            LibraryScanResult, resultado fixo do parsing.
        """
        return scan_result

    def fake_write_report(directory, tracks, errors) -> Path:
        """
        fake_write_report: registra destino sem criar diretório temporal.

        input:
            directory, tracks e errors do scan.

        output:
            Path, caminho do relatório simulado.
        """
        assert directory == tmp_path
        return report_path

    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))
    monkeypatch.setattr(keef, "scan_library", fake_scan)
    monkeypatch.setattr(keef, "create_output_dir", lambda root: None)
    monkeypatch.setattr(keef, "write_metadata_report", fake_write_report)

    exit_code = keef._run_scan(
        Namespace(directory=tmp_path, output_dir=None)
    )

    assert exit_code == 0
    assert str(report_path) in output.getvalue()


class FakePreviewClient(FakeClient):
    def __init__(self, report: ConnectionReport, search_result: SearchResult) -> None:
        """
        __init__: prepara cliente simulado para preview.

        input:
            report, relatório fixo de conexão.
            search_result, resposta fixa de pesquisa.

        output:
            None, inicializa o dublê com wait_for_search_responses.
        """
        super().__init__(report)
        self.search_result = search_result

    def search(self, request) -> SearchResult:
        """
        search: retorna pesquisa simulada.

        input:
            request, solicitação de pesquisa do keef.

        output:
            SearchResult, resultado fixo de pesquisa.
        """
        return self.search_result

    def wait_for_search_responses(self, search_id) -> list[dict]:
        """
        wait_for_search_responses: retorna respostas simuladas.

        input:
            search_id, identificador da pesquisa.

        output:
            list[dict], respostas incluídas na pesquisa.
        """
        return self.search_result.responses


def test_preview_online_saves_batch_plan(monkeypatch, tmp_path) -> None:
    """
    test_preview_online_saves_batch_plan: verifica preview online e saída JSON.

    input:
        relatório com uma track e candidato remoto elegível.

    output:
        None, teste aprovado quando plano JSON é salvo.
    """
    report_path = tmp_path / "metadata.json"
    report_path.write_text(
        '{"tracks": [{"path": "blue.mp3", "title": "Blue", "artist": "Artist", "bitrate_kbps": 192}]}'
    )
    output_path = tmp_path / "plan.json"
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
                            "bitrate": 320,
                        }
                    ],
                }
            ],
        }
    )

    def build_client(config) -> FakePreviewClient:
        """
        build_client: retorna cliente simulado.

        input:
            config, configuração recebida pela CLI.

        output:
            FakePreviewClient, cliente controlado pelo teste.
        """
        return FakePreviewClient(
            ConnectionReport(reachable=True, authenticated=True),
            search_result,
        )

    monkeypatch.setattr(keef, "SlskdClient", build_client)

    exit_code = keef._run_preview(
        Namespace(
            report=report_path,
            policy="higher",
            target_kbps=None,
            online=True,
            search_timeout=5,
            search_delay=0.0,
            output=output_path,
            verbose=False,
            url="http://localhost:5030",
            timeout=None,
        )
    )

    assert exit_code == 0
    assert output_path.exists()
    plan = json.loads(output_path.read_text())
    assert len(plan["tracks"]) == 1
    assert plan["tracks"][0]["username"] == "alice"
    assert plan["tracks"][0]["filename"] == "Artist - Blue.mp3"


def test_preview_online_saves_plan_next_to_report_by_default(monkeypatch, tmp_path) -> None:
    """
    test_preview_online_saves_plan_next_to_report_by_default: salva plan.json local.

    input:
        relatório em diretório temporário sem --output explícito.

    output:
        None, teste aprovado quando plan.json é criado ao lado do metadata.json.
    """
    report_dir = tmp_path / "batch-1"
    report_dir.mkdir()
    report_path = report_dir / "metadata.json"
    report_path.write_text(
        '{"tracks": [{"path": "blue.mp3", "title": "Blue", "artist": "Artist", "bitrate_kbps": 192}]}'
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
                            "bitrate": 320,
                        }
                    ],
                }
            ],
        }
    )

    def build_client(config) -> FakePreviewClient:
        """
        build_client: retorna cliente simulado.

        input:
            config, configuração recebida pela CLI.

        output:
            FakePreviewClient, cliente controlado pelo teste.
        """
        return FakePreviewClient(
            ConnectionReport(reachable=True, authenticated=True),
            search_result,
        )

    monkeypatch.setattr(keef, "SlskdClient", build_client)

    exit_code = keef._run_preview(
        Namespace(
            report=report_path,
            policy="higher",
            target_kbps=None,
            online=True,
            search_timeout=5,
            search_delay=0.0,
            output=None,
            verbose=False,
            url="http://localhost:5030",
            timeout=None,
        )
    )

    assert exit_code == 0
    plan_path = report_dir / "plan.json"
    assert plan_path.exists()
    plan = json.loads(plan_path.read_text())
    assert len(plan["tracks"]) == 1

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_rename_command_dry_run_shows_planned_renames(
    monkeypatch, tmp_path: Path
) -> None:
    """
    test_rename_command_dry_run_shows_planned_renames: protege dry-run do rename.

    input:
        diretório com um mp3 e metadados simulados.

    output:
        None, teste aprovado quando dry-run mostra o destino sem aplicar.
    """
    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))

    (tmp_path / "09 - What Do You See_.mp3").write_bytes(b"fake")

    def fake_read_audio(path):
        """
        fake_read_audio: retorna metadados fixos.

        input:
            path, caminho do arquivo.

        output:
            MusicTrack, metadados simulados.
        """
        return MusicTrack(
            path=str(path),
            title="What Do You See",
            artist="Wire",
            track_number=9,
        )

    monkeypatch.setattr("keef.rename.read_audio", fake_read_audio)

    exit_code = keef._run_rename(
        Namespace(directory=tmp_path, dry=True)
    )

    assert exit_code == 0
    assert "Renomeações: 1" in output.getvalue()
    assert "09. What Do You See - Wire.mp3" in output.getvalue()
    assert "Dry-run" in output.getvalue()
    assert (tmp_path / "09 - What Do You See_.mp3").exists()


def test_format_download_error_timeout() -> None:
    """
    test_format_download_error_timeout: descreve timeout de forma legível.

    input:
        exceção de timeout do httpx.

    output:
        None, teste aprovado quando a mensagem menciona peer offline.
    """
    import httpx

    message = keef._format_download_error(httpx.TimeoutException("timed out"))

    assert "peer" in message


def test_format_download_error_http_status_with_message() -> None:
    """
    test_format_download_error_http_status_with_message: extrai mensagem do slskd.

    input:
        resposta HTTP com corpo JSON contendo message.

    output:
        None, teste aprovado quando a mensagem do slskd aparece.
    """
    import httpx
    from unittest.mock import Mock

    request = Mock()
    response = Mock()
    response.status_code = 400
    response.json.return_value = {"message": "peer not found"}
    error = httpx.HTTPStatusError("bad", request=request, response=response)

    message = keef._format_download_error(error)

    assert "peer not found" in message


def test_format_download_error_http_status_without_body() -> None:
    """
    test_format_download_error_http_status_without_body: mostra status HTTP.

    input:
        resposta HTTP sem corpo JSON interpretável.

    output:
        None, teste aprovado quando a mensagem contém o código.
    """
    import httpx
    from unittest.mock import Mock

    request = Mock()
    response = Mock()
    response.status_code = 503
    response.json.side_effect = ValueError("não é json")
    error = httpx.HTTPStatusError("bad", request=request, response=response)

    message = keef._format_download_error(error)

    assert "503" in message


def test_rename_command_applies_renames(monkeypatch, tmp_path: Path) -> None:
    """
    test_rename_command_applies_renames: aplica renomeações no filesystem.

    input:
        diretório com um mp3 e metadados simulados.

    output:
        None, teste aprovado quando o arquivo é renomeado no disco.
    """
    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))

    (tmp_path / "09 - What Do You See_.mp3").write_bytes(b"fake")

    def fake_read_audio(path):
        """
        fake_read_audio: retorna metadados fixos.

        input:
            path, caminho do arquivo.

        output:
            MusicTrack, metadados simulados.
        """
        return MusicTrack(
            path=str(path),
            title="What Do You See",
            artist="Wire",
            track_number=9,
        )

    monkeypatch.setattr("keef.rename.read_audio", fake_read_audio)

    exit_code = keef._run_rename(
        Namespace(directory=tmp_path, dry=False)
    )

    assert exit_code == 0
    assert "Renomeados: 1" in output.getvalue()
    assert not (tmp_path / "09 - What Do You See_.mp3").exists()
    assert (tmp_path / "09. What Do You See - Wire.mp3").exists()


def _accepted_item(title: str, artist: str) -> BatchPreviewItem:
    """
    _accepted_item: cria item de preview com candidato aceito.

    input:
        title, título da faixa local.
        artist, artista da faixa local.

    output:
        BatchPreviewItem, item com candidato aceito e elegível.
    """
    track = MusicTrack(path=f"{title}.mp3", title=title, artist=artist)
    candidate = SearchCandidate(
        username="alice",
        filename=f"{artist} - {title}.mp3",
        size=1_000,
    )
    match = MatchResult(
        candidate=candidate,
        score=0.9,
        accepted=True,
        ambiguous=False,
    )

    return BatchPreviewItem(
        track=track,
        candidates=[match],
        quality_decisions=[QualityDecision(eligible=True, reason="ok")],
    )


def _missing_item(title: str, artist: str) -> BatchPreviewItem:
    """
    _missing_item: cria item de preview sem candidato aceito.

    input:
        title, título da faixa local.
        artist, artista da faixa local.

    output:
        BatchPreviewItem, item sem candidatos.
    """
    track = MusicTrack(path=f"{title}.mp3", title=title, artist=artist)

    return BatchPreviewItem(track=track, candidates=[], quality_decisions=[])


def test_render_missing_summary_lists_missing_tracks(monkeypatch) -> None:
    """
    test_render_missing_summary_lists_missing_tracks: lista faixas ausentes.

    input:
        itens com uma aceita e duas não encontradas.

    output:
        None, teste aprovado quando o bloco final mostra as ausentes.
    """
    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))

    items = [
        _accepted_item("Blue", "Artist"),
        _missing_item("Getr", "A L E X"),
        _missing_item("Already named", "a l e x"),
    ]

    keef._render_missing_summary(items)

    rendered = output.getvalue()
    assert "Não encontradas: 2" in rendered
    assert "Getr — A L E X" in rendered
    assert "Already named — a l e x" in rendered
    assert "Blue" not in rendered


def test_render_missing_summary_all_found(monkeypatch) -> None:
    """
    test_render_missing_summary_all_found: confirma quando tudo foi achado.

    input:
        itens todos com candidato aceito.

    output:
        None, teste aprovado quando a mensagem é positiva.
    """
    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))

    items = [_accepted_item("Blue", "Artist")]

    keef._render_missing_summary(items)

    rendered = output.getvalue()
    assert "Todas as faixas foram encontradas" in rendered


def test_render_missing_summary_keeps_error_detail(monkeypatch) -> None:
    """
    test_render_missing_summary_keeps_error_detail: preserva mensagem de erro.

    input:
        item com erro de pesquisa.

    output:
        None, teste aprovado quando o detalhe do erro aparece.
    """
    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))

    track = MusicTrack(path="broken.mp3", title="Broken", artist="Artist")
    items = [BatchPreviewItem(track=track, error="falha de rede")]

    keef._render_missing_summary(items)

    rendered = output.getvalue()
    assert "Não encontradas: 1" in rendered
    assert "Broken — Artist" in rendered
    assert "falha de rede" in rendered


def test_print_preview_header_shows_online_mode(monkeypatch) -> None:
    """
    test_print_preview_header_shows_online_mode: mostra modo online no cabeçalho.

    input:
        flag online verdadeira.

    output:
        None, teste aprovado quando o cabeçalho contém o modo.
    """
    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))

    keef._print_preview_header(True)

    rendered = output.getvalue()
    assert "keef: preview" in rendered
    assert "--online" in rendered
    assert "━" in rendered


def test_print_preview_header_shows_offline_mode(monkeypatch) -> None:
    """
    test_print_preview_header_shows_offline_mode: mostra modo offline.

    input:
        flag online falsa.

    output:
        None, teste aprovado quando o cabeçalho contém --offline.
    """
    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))

    keef._print_preview_header(False)

    assert "--offline" in output.getvalue()


def test_render_preview_skips_tracks_without_accepted(monkeypatch) -> None:
    """
    test_render_preview_skips_tracks_without_accepted: omite faixas sem aceitos.

    input:
        uma faixa com candidato aceito e uma sem nenhum.

    output:
        None, teste aprovado quando a sem aceito não aparece no bloco.
    """
    output = StringIO()
    monkeypatch.setattr(keef, "console", Console(file=output, force_terminal=False))

    items = [
        _accepted_item("Blue", "Artist"),
        _missing_item("late", "A L E X"),
    ]

    keef._render_preview(items)

    rendered = output.getvalue()
    assert "Blue" in rendered
    assert "late" not in rendered


def test_save_batch_plan_skips_empty_plan(tmp_path: Path) -> None:
    """
    test_save_batch_plan_skips_empty_plan: não grava plano sem candidatos.

    input:
        itens sem nenhum candidato aceito.

    output:
        None, teste aprovado quando retorna False e não cria arquivo.
    """
    plan_path = tmp_path / "plan.json"
    items = [_missing_item("late", "A L E X")]

    saved = keef._save_batch_plan(plan_path, items)

    assert saved is False
    assert not plan_path.exists()


def test_save_batch_plan_writes_when_accepted(tmp_path: Path) -> None:
    """
    test_save_batch_plan_writes_when_accepted: grava plano com candidatos.

    input:
        item com candidato aceito.

    output:
        None, teste aprovado quando retorna True e cria o arquivo.
    """
    plan_path = tmp_path / "plan.json"
    items = [_accepted_item("Blue", "Artist")]

    saved = keef._save_batch_plan(plan_path, items)

    assert saved is True
    assert plan_path.exists()
    payload = json.loads(plan_path.read_text())
    assert len(payload["tracks"]) == 1

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
