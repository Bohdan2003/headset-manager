import json

import pytest
from fastapi.testclient import TestClient

from headset_server import create_app
from headset_server.config import Settings

ADMIN = "test-admin-token"


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        admin_token=ADMIN,
        offline_after_s=1,
        state_snapshot_s=1,
        hello_timeout_s=1.0,
        dashboard_dir=str(tmp_path / "no-dashboard"),
        auth_enabled=False,
        auth_file=str(tmp_path / "auth.json"),
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


def register(client: TestClient, serial: str = "SERIAL-1", label: str = "Шлем 01") -> dict:
    r = client.post(
        "/api/headsets",
        json={"label": label, "serial": serial},
        headers={"Authorization": f"Bearer {ADMIN}"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def hello(creds: dict) -> str:
    return json.dumps(
        {"type": "hello", "headsetId": creds["headsetId"], "token": creds["token"], "agentVersion": "0.0.1"}
    )


def heartbeat(battery: int = 77, current_pkg: str | None = "com.Anvio.CityZ") -> str:
    return json.dumps(
        {
            "type": "heartbeat",
            "battery": battery,
            "charging": False,
            "currentPkg": current_pkg,
            "adb": "waiting_confirmation",
            "sleepDisabled": True,
        }
    )
