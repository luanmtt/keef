from uuid import UUID

import httpx

from keef.config import SlskdConfig
from keef.models import ConnectionReport
from keef.models import SearchRequest
from keef.slskd import SlskdClient

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_client(handler):
    """
    build_client: cria cliente com transporte simulado.

    input:
        handler, função que responde às requisições HTTP.

    output:
        SlskdClient, cliente configurado para teste.
    """
    config = SlskdConfig.model_validate({"base_url": "http://testserver"})
    transport = httpx.MockTransport(handler)

    return SlskdClient(config, transport=transport)


def test_get_status_returns_connected_report() -> None:
    """
    test_get_status_returns_connected_report: converte respostas válidas.

    input:
        respostas simuladas de aplicação e servidor.

    output:
        None, teste aprovado quando a conexão ativa é identificada.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        """
        handler: responde às rotas simuladas.

        input:
            request, requisição HTTP.

        output:
            httpx.Response, resposta JSON simulada.
        """
        if request.url.path.endswith("/application"):
            return httpx.Response(200, json={"state": "running"})

        return httpx.Response(
            200,
            json={"isConnected": True, "isLoggedIn": True, "username": "alice"},
        )

    client = build_client(handler)

    try:
        report = client.get_status()
    finally:
        client.close()

    assert report == ConnectionReport(
        reachable=True,
        authenticated=True,
        soulseek_connected=True,
        account="alice",
    )


def test_get_status_handles_authentication_failure() -> None:
    """
    test_get_status_handles_authentication_failure: classifica 401.

    input:
        resposta HTTP 401.

    output:
        None, teste aprovado quando o relatório indica não autenticado.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        """
        handler: rejeita a requisição simulada.

        input:
            request, requisição HTTP.

        output:
            httpx.Response, resposta 401.
        """
        return httpx.Response(401)

    client = build_client(handler)

    try:
        report = client.get_status()
    finally:
        client.close()

    assert report.reachable is True
    assert report.authenticated is False


def test_get_status_handles_malformed_server_payload() -> None:
    """
    test_get_status_handles_malformed_server_payload: classifica payload incompatível.

    input:
        JSON inválido para o modelo de servidor.

    output:
        None, teste aprovado quando o erro é legível.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        """
        handler: entrega payload inválido.

        input:
            request, requisição HTTP.

        output:
            httpx.Response, JSON incompatível.
        """
        if request.url.path.endswith("/application"):
            return httpx.Response(200, json={})

        return httpx.Response(200, json=["invalid"])

    client = build_client(handler)

    try:
        report = client.get_status()
    finally:
        client.close()

    assert report.reachable is False
    assert "objeto JSON" in (report.detail or "")


def test_search_sends_expected_payload() -> None:
    """
    test_search_sends_expected_payload: verifica criação de pesquisa.

    input:
        solicitação com texto e limites de busca.

    output:
        None, teste aprovado quando payload e UUID são processados.
    """
    search_id = "12345678-1234-5678-1234-567812345678"

    def handler(request: httpx.Request) -> httpx.Response:
        """
        handler: valida requisição de pesquisa simulada.

        input:
            request, requisição HTTP.

        output:
            httpx.Response, pesquisa criada.
        """
        assert request.method == "POST"
        assert request.url.path.endswith("/searches")
        assert request.read() == b'{"searchText":"Artist Blue","searchTimeout":5,"responseLimit":10}'

        return httpx.Response(200, json={"id": search_id, "responses": []})

    client = build_client(handler)

    try:
        result = client.search(
            SearchRequest.model_validate(
                {"search_text": "Artist Blue", "search_timeout": 5, "response_limit": 10}
            )
        )
    finally:
        client.close()

    assert str(result.id) == search_id


def test_get_search_responses_accepts_list_payload() -> None:
    """
    test_get_search_responses_accepts_list_payload: lê respostas de pesquisa.

    input:
        lista JSON simulada retornada pelo endpoint.

    output:
        None, teste aprovado quando objetos são preservados.
    """
    search_id = "12345678-1234-5678-1234-567812345678"

    def handler(request: httpx.Request) -> httpx.Response:
        """
        handler: retorna respostas simuladas.

        input:
            request, requisição HTTP.

        output:
            httpx.Response, lista de respostas.
        """
        return httpx.Response(200, json=[{"username": "alice", "files": []}])

    client = build_client(handler)

    try:
        responses = client.get_search_responses(UUID(search_id))
    finally:
        client.close()

    assert responses == [{"username": "alice", "files": []}]


def test_get_download_status_uses_encoded_username() -> None:
    """
    test_get_download_status_uses_encoded_username: consulta estado de download.

    input:
        usuário com espaço e identificador de download.

    output:
        None, teste aprovado quando rota e payload são processados.
    """
    def handler(request: httpx.Request) -> httpx.Response:
        """
        handler: responde estado de transferência simulado.

        input:
            request, requisição HTTP.

        output:
            httpx.Response, estado queued.
        """
        assert request.url.raw_path.endswith(b"/alice%20smith/transfer-1")
        return httpx.Response(200, json={"id": "transfer-1", "state": "queued"})

    client = build_client(handler)

    try:
        status = client.get_download_status("alice smith", "transfer-1")
    finally:
        client.close()

    assert status["state"] == "queued"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
