import os

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SlskdConfig(BaseModel):
    base_url: AnyHttpUrl
    api_token: SecretStr | None = None
    timeout_seconds: float = Field(default=10.0, gt=0)

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
            "base_url": os.getenv("KEEF_SLSKD_URL"),
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
