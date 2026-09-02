import httpx

from keef.config import SlskdConfig
from keef.models import ConnectionReport
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
