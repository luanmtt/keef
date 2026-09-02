from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ConnectionState(StrEnum):
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"


class SlskdStatus(BaseModel):
    model_config = ConfigDict(extra="allow")

    soulseek_connected: bool | None = None
    username: str | None = None
    state: ConnectionState = ConnectionState.UNKNOWN


class SlskdServerState(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    is_connected: bool | None = Field(default=None, alias="isConnected")
    is_logged_in: bool | None = Field(default=None, alias="isLoggedIn")
    username: str | None = None


class ConnectionReport(BaseModel):
    reachable: bool
    authenticated: bool | None = None
    soulseek_connected: bool | None = None
    account: str | None = None
    detail: str | None = None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
