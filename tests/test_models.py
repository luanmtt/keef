import pytest
from pydantic import ValidationError

from keef.config import SlskdConfig
from keef.models import ConnectionState, SlskdStatus

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def test_config_accepts_valid_values() -> None:
    """
    test_config_accepts_valid_values: valida configuração correta.

    input:
        valores válidos de URL, token e timeout.

    output:
        None, teste aprovado quando o modelo é criado.
    """
    config = SlskdConfig.model_validate(
        {
            "base_url": "http://localhost:5030",
            "api_token": "secret",
            "timeout_seconds": 5,
        }
    )

    assert str(config.base_url) == "http://localhost:5030/"
    assert config.timeout_seconds == 5


def test_config_rejects_invalid_url() -> None:
    """
    test_config_rejects_invalid_url: rejeita URL inválida.

    input:
        URL malformada.

    output:
        None, teste aprovado quando ocorre ValidationError.
    """
    with pytest.raises(ValidationError):
        SlskdConfig.model_validate({"base_url": "not-a-url"})


def test_config_rejects_non_positive_timeout() -> None:
    """
    test_config_rejects_non_positive_timeout: rejeita timeout inválido.

    input:
        timeout não positivo.

    output:
        None, teste aprovado quando ocorre ValidationError.
    """
    with pytest.raises(ValidationError):
        SlskdConfig.model_validate(
            {"base_url": "http://localhost:5030", "timeout_seconds": 0}
        )


def test_config_safe_dict_redacts_token() -> None:
    """
    test_config_safe_dict_redacts_token: remove token da saída pública.

    input:
        configuração contendo segredo.

    output:
        None, teste aprovado quando o token é ocultado.
    """
    config = SlskdConfig.model_validate(
        {"base_url": "http://localhost:5030", "api_token": "secret"}
    )

    safe_values = config.safe_dict()

    assert safe_values["api_token"] == "[redacted]"


def test_status_accepts_unknown_extra_fields() -> None:
    """
    test_status_accepts_unknown_extra_fields: aceita campos extras.

    input:
        payload parcial com campo desconhecido.

    output:
        None, teste aprovado quando o campo é preservado.
    """
    status = SlskdStatus.model_validate(
        {
            "soulseek_connected": True,
            "username": "test-user",
            "unexpected_field": "preserved",
        }
    )

    assert status.state is ConnectionState.UNKNOWN
    assert status.model_extra is not None
    assert status.model_extra["unexpected_field"] == "preserved"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
