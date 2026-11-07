import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from headset_server import create_app

from .conftest import ADMIN, hello, register

PASSWORD = "correct horse"


@pytest.fixture
def auth_settings(settings):
    settings.auth_enabled = True
    return settings


@pytest.fixture
def client(auth_settings):
    with TestClient(create_app(auth_settings)) as c:
        yield c


def login(c, password=PASSWORD):
    return c.post("/api/auth/login", json={"password": password})


def setup(c):
    assert c.post("/api/auth/setup", json={"password": PASSWORD}).status_code == 204


def test_everything_closed_until_logged_in(client):
    setup(client)
    client.cookies.clear()
    assert client.get("/api/auth/status").json() == {"configured": True, "authenticated": False, "canSetup": True}
    for path in ("/api/headsets", "/api/stats", "/api/setup"):
        assert client.get(path).status_code == 401
    assert client.post("/api/commands", json={"headsetIds": ["x"], "cmd": "sleep", "params": {}}).status_code == 401
    assert client.patch("/api/headsets/x", json={"label": "y"}).status_code == 401
    assert client.post("/api/setup/update-wifi", json={"headsetIds": ["x"]}).status_code == 401
    with client.websocket_connect("/live") as ws:
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_json()
    assert e.value.code == 4401


def test_login_opens_access_and_logout_closes_it(client):
    setup(client)
    client.cookies.clear()
    assert login(client, "wrong password").status_code == 401
    assert login(client).status_code == 204
    assert client.get("/api/headsets").status_code == 200
    with client.websocket_connect("/live") as ws:
        assert ws.receive_json()["type"] == "snapshot"
    client.post("/api/auth/logout")
    assert client.get("/api/headsets").status_code == 401


def test_password_is_set_once_and_only_on_server_computer(auth_settings):
    with TestClient(create_app(auth_settings), client=("192.168.50.20", 5000)) as remote:
        assert remote.get("/api/auth/status").json()["canSetup"] is False
        assert remote.post("/api/auth/setup", json={"password": PASSWORD}).status_code == 403
    with TestClient(create_app(auth_settings)) as local:
        assert local.post("/api/auth/setup", json={"password": "short"}).status_code == 422
        setup(local)
        assert local.post("/api/auth/setup", json={"password": "other password"}).status_code == 409


def test_password_is_not_stored_in_plain_text(client, auth_settings, tmp_path):
    setup(client)
    assert PASSWORD not in (tmp_path / "auth.json").read_text()


def test_session_survives_restart_reset_signs_out(auth_settings):
    with TestClient(create_app(auth_settings)) as c:
        setup(c)
        cookies = dict(c.cookies)
    with TestClient(create_app(auth_settings), cookies=cookies) as c:
        assert c.get("/api/headsets").status_code == 200
        c.app.state.auth.reset()
        assert c.get("/api/auth/status").json()["configured"] is False
        assert c.get("/api/headsets").status_code == 401


def test_forged_cookie_is_rejected(client):
    setup(client)
    client.cookies.clear()
    client.cookies.set("arena_session", "99999999999.deadbeef")
    assert client.get("/api/headsets").status_code == 401


def test_too_many_wrong_passwords_lock_login(client):
    setup(client)
    client.cookies.clear()
    for _ in range(5):
        assert login(client, "wrong password").status_code == 401
    assert login(client).status_code == 429  # даже верный пароль: адрес временно заблокирован


def test_agent_and_provisioning_do_not_need_password(client):
    setup(client)
    client.cookies.clear()
    creds = register(client)  # админский токен, как в provision.sh
    with client.websocket_connect("/agent") as ws:
        ws.send_text(hello(creds))
        assert ws.receive_json()["type"] == "welcome"
    r = client.get("/api/headsets", headers={"Authorization": f"Bearer {ADMIN}"})
    assert r.status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/api/agent/apk").status_code in (200, 404)
