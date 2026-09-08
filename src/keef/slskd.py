from typing import Any
from uuid import UUID
from urllib.parse import quote
import time

import httpx

from keef.config import SlskdConfig
from keef.models import ConnectionReport, SearchRequest, SearchResult, SlskdServerState

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

    def search(self, request: SearchRequest) -> SearchResult:
        """
        search: inicia uma pesquisa na rede Soulseek.

        input:
            request, texto e opções validados da pesquisa.

        output:
            SearchResult, pesquisa criada pelo slskd.
        """
        # slskd 0.26.0 trata searchTimeout como milissegundos, apesar da
        # documentação indicar segundos. Multiplicamos por 1000 para manter a
        # CLI em segundos e a API no formato que o slskd espera.
        payload = self._post_json(
            "/api/v0/searches",
            {
                "searchText": request.search_text,
                "searchTimeout": request.search_timeout * 1000,
                "responseLimit": request.response_limit,
            },
        )

        return SearchResult.model_validate(payload)

    def get_search_responses(self, search_id: UUID) -> list[dict[str, Any]]:
        """
        get_search_responses: obtém respostas detalhadas de uma pesquisa.

        input:
            search_id, identificador UUID da pesquisa.

        output:
            list[dict[str, Any]], respostas de busca validadas como objetos.
        """
        payload = self._request_json(f"/api/v0/searches/{search_id}/responses")

        if isinstance(payload, dict):
            responses = payload.get("responses", payload)
        else:
            responses = payload

        if not isinstance(responses, list) or not all(isinstance(item, dict) for item in responses):
            raise TypeError("As respostas da pesquisa não são uma lista de objetos.")

        return responses

    def wait_for_search_responses(
        self,
        search_id: UUID,
        min_responses: int = 1,
        poll_seconds: float = 1.0,
        max_wait_seconds: float = 15.0,
    ) -> list[dict[str, Any]]:
        """
        wait_for_search_responses: aguarda respostas de uma pesquisa ativa.

        input:
            search_id, identificador UUID da pesquisa.
            min_responses, número mínimo de respostas desejado.
            poll_seconds, intervalo entre consultas.
            max_wait_seconds, tempo máximo de espera.

        output:
            list[dict[str, Any]], respostas acumuladas até o critério ou timeout.
        """
        deadline = time.monotonic() + max_wait_seconds

        while True:
            responses = self.get_search_responses(search_id)

            if len(responses) >= min_responses:
                return responses

            if time.monotonic() >= deadline:
                return responses

            if poll_seconds > 0:
                time.sleep(poll_seconds)

    def enqueue_download(
        self,
        username: str,
        filename: str,
        size: int,
        destination: str,
    ) -> dict[str, Any]:
        """
        enqueue_download: solicita um download individual em staging.

        input:
            username, usuário que possui o arquivo.
            filename, caminho remoto do arquivo.
            size, tamanho esperado em bytes.
            destination, pasta relativa de destino no slskd.

        output:
            dict[str, Any], resposta da fila de downloads.
        """
        return self._post_json(
            f"/api/v0/transfers/downloads/batches",
            {
                "username": username,
                "files": [{"filename": filename, "size": size}],
                "options": {"destination": destination},
            },
        )

    def get_download_status(self, username: str, download_id: str) -> dict[str, Any]:
        """
        get_download_status: consulta estado de um download.

        input:
            username, usuário que possui o arquivo.
            download_id, identificador do download no slskd.

        output:
            dict[str, Any], estado retornado pela API.
        """
        encoded_username = quote(username, safe="")
        return self._get_json(f"/api/v0/transfers/downloads/{encoded_username}/{download_id}")

    def list_downloads(self) -> list[dict[str, Any]]:
        """
        list_downloads: lista todos os downloads ativos.

        input:
            nenhum.

        output:
            list[dict[str, Any]], downloads em andamento.
        """
        payload = self._request_json("/api/v0/transfers/downloads")

        if isinstance(payload, list):
            return payload

        return []

    def get_user_info(self, username: str) -> dict[str, Any]:
        """
        get_user_info: consulta informações de um usuário.

        input:
            username, nome do usuário.

        output:
            dict[str, Any], dados do usuário (status, velocidade, etc.).
        """
        encoded_username = quote(username, safe="")
        return self._get_json(f"/api/v0/users/{encoded_username}")

    def _get_json(self, path: str) -> dict[str, Any]:
        """
        _get_json: obtém um objeto JSON de uma rota.

        input:
            path, caminho relativo da API.

        output:
            dict[str, Any], payload JSON validado como objeto.
        """
        payload = self._request_json(path)

        if not isinstance(payload, dict):
            raise TypeError("A resposta da API não é um objeto JSON.")

        return payload

    def _request_json(self, path: str) -> Any:
        """
        _request_json: executa GET e decodifica JSON sem restringir o formato.

        input:
            path, caminho relativo da API.

        output:
            Any, payload JSON retornado pelo slskd.
        """
        response = self._http.get(path)
        response.raise_for_status()

        return response.json()

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """
        _post_json: envia payload JSON para uma rota.

        input:
            path, caminho relativo da API.
            payload, corpo JSON da requisição.

        output:
            dict[str, Any], resposta JSON validada como objeto.
        """
        response = self._http.post(path, json=payload)
        response.raise_for_status()
        response_payload = response.json()

        if not isinstance(response_payload, dict):
            raise TypeError("A resposta da API não é um objeto JSON.")

        return response_payload

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
