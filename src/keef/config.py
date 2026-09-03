import os
import json
from pathlib import Path

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEFAULT_SLSKD_URL = "http://127.0.0.1:5030"
CONFIG_PATH = Path.home() / ".config" / "keef" / "config.json"


class SlskdConfig(BaseModel):
    base_url: AnyHttpUrl = Field(default=DEFAULT_SLSKD_URL)
    api_token: SecretStr | None = None
    timeout_seconds: float = Field(default=10.0, gt=0)

    @classmethod
    def from_sources(
        cls,
        url: str | None = None,
        token: str | None = None,
        timeout: float | None = None,
        persist_url: bool = False,
    ) -> "SlskdConfig":
        """
        from_sources: combina argumentos, ambiente e configuração salva.

        input:
            url, URL fornecida nesta execução.
            token, token fornecido nesta execução.
            timeout, timeout fornecido nesta execução.
            persist_url, indica se a URL explícita deve ser salva.

        output:
            SlskdConfig, configuração validada para o cliente.
        """
        saved_url = load_saved_url()
        selected_url = url or os.getenv("KEEF_SLSKD_URL") or saved_url

        if url is not None and persist_url:
            save_url(url)

        return cls.model_validate(
            {
                "base_url": selected_url or DEFAULT_SLSKD_URL,
                "api_token": token or os.getenv("KEEF_SLSKD_TOKEN"),
                "timeout_seconds": timeout
                if timeout is not None
                else os.getenv("KEEF_SLSKD_TIMEOUT", "10"),
            }
        )

    @classmethod
    def from_env(cls) -> "SlskdConfig":
        """
        from_env: carrega a configuração do slskd.

        input:
            ambiente do processo.

        output:
            SlskdConfig, configuração validada.
        """
        values = {
            "base_url": os.getenv("KEEF_SLSKD_URL", DEFAULT_SLSKD_URL),
            "api_token": os.getenv("KEEF_SLSKD_TOKEN"),
            "timeout_seconds": os.getenv("KEEF_SLSKD_TIMEOUT", "10"),
        }

        return cls.model_validate(values)

    def safe_dict(self) -> dict[str, object]:
        """
        safe_dict: exporta a configuração sem expor segredos.

        input:
            self, configuração atual.

        output:
            dict[str, object], valores seguros para exibição ou logging.
        """
        values = self.model_dump()

        if self.api_token is not None:
            values["api_token"] = "[redacted]"

        return values


def load_saved_url() -> str | None:
    """
    load_saved_url: lê a URL persistida do slskd.

    input:
        CONFIG_PATH, caminho do arquivo de configuração do usuário.

    output:
        str | None, URL salva ou None quando não existe/é inválida.
    """
    try:
        values = json.loads(CONFIG_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None

    url = values.get("slskd_url") if isinstance(values, dict) else None

    return url if isinstance(url, str) else None


def save_url(url: str) -> None:
    """
    save_url: persiste a URL do slskd para próximas execuções.

    input:
        url, endereço da API a ser salvo.

    output:
        None, grava a configuração no diretório do usuário.
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"slskd_url": url}, indent=2) + "\n")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
