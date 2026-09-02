from typing import Any

import httpx

from keef.config import SlskdConfig
from keef.models import ConnectionReport, SlskdServerState

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SlskdClientError(Exception):
    """Indica uma falha ao comunicar com a API do slskd."""


class SlskdClient:
    def __init__(
        self,
        config: SlskdConfig,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """
        __init__: inicializa o cliente HTTP do slskd.

        input:
            config, configuração validada do slskd.
            transport, transporte HTTP opcional para testes.

        output:
            None, inicializa o cliente no objeto atual.
        """
        headers = {}

        if config.api_token is not None:
            headers["X-API-Key"] = config.api_token.get_secret_value()

        self._http = httpx.Client(
            base_url=str(config.base_url).rstrip("/"),
            headers=headers,
            timeout=config.timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        """
        close: fecha a conexão HTTP.

        input:
            self, cliente HTTP atual.

        output:
            None.
        """
        self._http.close()

    def get_status(self) -> ConnectionReport:
        """
        get_status: consulta a aplicação e o servidor do slskd.

        input:
            self, cliente HTTP configurado.

        output:
            ConnectionReport, relatório de conexão e autenticação.
        """
        try:
            self._get_json("/api/v0/application")
            server_payload = self._get_json("/api/v0/server")
        except httpx.HTTPStatusError as error:
            if error.response.status_code in {401, 403}:
                return ConnectionReport(
                    reachable=True,
                    authenticated=False,
                    detail="Autenticação rejeitada pela API do slskd.",
                )

            return ConnectionReport(
                reachable=True,
                detail=f"A API do slskd respondeu HTTP {error.response.status_code}.",
            )
        except httpx.TimeoutException:
            return ConnectionReport(
                reachable=False,
                detail="Tempo esgotado ao contactar a API do slskd.",
            )
        except (httpx.HTTPError, ValueError, TypeError) as error:
            return ConnectionReport(
                reachable=False,
                detail=f"Falha ao contactar a API do slskd: {error}.",
            )

        try:
            server_state = SlskdServerState.model_validate(server_payload)
        except (ValueError, TypeError) as error:
            return ConnectionReport(
                reachable=True,
                authenticated=True,
                detail=f"Resposta de estado inválida: {error}.",
            )

        return ConnectionReport(
            reachable=True,
            authenticated=True,
            soulseek_connected=server_state.is_connected,
            account=server_state.username,
        )

    def _get_json(self, path: str) -> dict[str, Any]:
        """
        _get_json: obtém um objeto JSON de uma rota.

        input:
            path, caminho relativo da API.

        output:
            dict[str, Any], payload JSON validado como objeto.
        """
        response = self._http.get(path)
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, dict):
            raise TypeError("A resposta da API não é um objeto JSON.")

        return payload

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
