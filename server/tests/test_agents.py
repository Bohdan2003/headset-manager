import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from headset_server import create_app

from .conftest import heartbeat, hello, register


def headset(client, headset_id):
    return next(h for h in client.get("/api/headsets").json() if h["id"] == headset_id)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_register_requires_admin_token(client):
    r = client.post("/api/headsets", json={"label": "X", "serial": "S"})
    assert r.status_code == 401
    r = client.post("/api/headsets", json={"label": "X", "serial": "S"}, headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_new_headset_is_offline(client):
    creds = register(client)
    assert creds["created"] is True
    h = headset(client, creds["headsetId"])
    assert h["online"] is False
    assert h["label"] == "Шлем 01"


def test_agent_heartbeat_makes_headset_online_with_battery(client):
    creds = register(client)
    with client.websocket_connect("/agent") as ws:
        ws.send_text(hello(creds))
        welcome = ws.receive_json()
        assert welcome["type"] == "welcome"
        assert welcome["heartbeatIntervalS"] == 5

        ws.send_text(heartbeat(battery=77))
        time.sleep(0.2)
        h = headset(client, creds["headsetId"])
        assert h["online"] is True
        assert h["battery"] == 77
        assert h["currentPkg"] == "com.Anvio.CityZ"
        assert h["adb"] == "waiting_confirmation"
        assert h["agentVersion"] == "0.0.1"

    time.sleep(0.2)
    assert headset(client, creds["headsetId"])["online"] is False


def test_wrong_token_is_rejected(client):
    creds = register(client)
    creds["token"] = "wrong"
    with client.websocket_connect("/agent") as ws:
        ws.send_text(hello(creds))
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_text()
    assert e.value.code == 4401
    assert headset(client, creds["headsetId"])["online"] is False


def test_first_message_must_be_hello(client):
    register(client)
    with client.websocket_connect("/agent") as ws:
        ws.send_text(heartbeat())
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_text()
    assert e.value.code == 4400


def test_bad_message_does_not_drop_connection(client):
    creds = register(client)
    with client.websocket_connect("/agent") as ws:
        ws.send_text(hello(creds))
        ws.receive_json()
        ws.send_text('{"type": "heartbeat", "battery": 999}')  # не проходит проверку
        ws.send_text(heartbeat(battery=50))
        time.sleep(0.2)
        h = headset(client, creds["headsetId"])
        assert h["online"] is True
        assert h["battery"] == 50


def test_silent_agent_goes_offline(client):
    creds = register(client)
    with client.websocket_connect("/agent") as ws:
        ws.send_text(hello(creds))
        ws.receive_json()
        time.sleep(2.5)  # offline_after_s=1, проверка раз в секунду
        assert headset(client, creds["headsetId"])["online"] is False
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_text()
        assert e.value.code == 4408


def test_reconnect_replaces_old_connection(client):
    creds = register(client)
    with client.websocket_connect("/agent") as old:
        old.send_text(hello(creds))
        old.receive_json()
        with client.websocket_connect("/agent") as new:
            new.send_text(hello(creds))
            new.receive_json()
            with pytest.raises(WebSocketDisconnect) as e:
                old.receive_text()
            assert e.value.code == 4409
            time.sleep(0.2)
            assert headset(client, creds["headsetId"])["online"] is True


def test_reprovision_same_serial_keeps_id_and_rotates_token(client):
    first = register(client, serial="SER-9", label="Шлем 09")
    second = register(client, serial="SER-9", label="Шлем 09 (после сброса)")
    assert second["created"] is False
    assert second["headsetId"] == first["headsetId"]
    assert second["token"] != first["token"]

    with client.websocket_connect("/agent") as ws:  # старый токен больше не действует
        ws.send_text(hello(first))
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_text()
    assert e.value.code == 4401


def test_live_gets_snapshot_and_updates(client):
    creds = register(client)
    with client.websocket_connect("/live") as live:
        snap = live.receive_json()
        assert snap["type"] == "snapshot"
        assert [h["id"] for h in snap["headsets"]] == [creds["headsetId"]]

        with client.websocket_connect("/agent") as ws:
            ws.send_text(hello(creds))
            ws.receive_json()
            update = live.receive_json()
            assert update["type"] == "headset"
            assert update["headset"]["online"] is True

            ws.send_text(heartbeat(battery=42))
            update = live.receive_json()
            assert update["headset"]["battery"] == 42


def test_state_survives_restart(settings):
    with TestClient(create_app(settings)) as c:
        creds = register(c)
        with c.websocket_connect("/agent") as ws:
            ws.send_text(hello(creds))
            ws.receive_json()
            ws.send_text(heartbeat(battery=33))
            time.sleep(0.2)

    with TestClient(create_app(settings)) as c:
        h = headset(c, creds["headsetId"])
        assert h["online"] is False  # после перезапуска все офлайн, пока не подключатся
        assert h["battery"] == 33    # но последнее известное состояние сохранено


def test_serves_built_dashboard_without_hiding_api(settings, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>dashboard</title>")
    settings.dashboard_dir = str(dist)
    with TestClient(create_app(settings)) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "dashboard" in r.text
        assert c.get("/api/headsets").json() == []
        assert c.get("/health").json() == {"status": "ok"}


def test_controllers_from_heartbeat(client):
    import json

    creds = register(client)
    with client.websocket_connect("/agent") as ws:
        ws.send_text(hello(creds))
        ws.receive_json()
        hb = json.loads(heartbeat())
        hb["controllers"] = [
            {"side": "right", "battery": 40, "connected": True},
            {"side": "left", "battery": 50, "connected": False},
        ]
        ws.send_text(json.dumps(hb))
        time.sleep(0.2)
        assert headset(client, creds["headsetId"])["controllers"] == [
            {"side": "left", "battery": 50, "connected": False},
            {"side": "right", "battery": 40, "connected": True},
        ]
        ws.send_text(heartbeat())  # старый агент без controllers — последние известные остаются
        time.sleep(0.2)
        assert len(headset(client, creds["headsetId"])["controllers"]) == 2


def test_rename_headset(client):
    creds = register(client)
    with client.websocket_connect("/live") as live:
        live.receive_json()
        r = client.patch(f"/api/headsets/{creds['headsetId']}", json={"label": "  Шлем у входа  "})
        assert r.status_code == 204
        update = live.receive_json()
        assert update["headset"]["label"] == "Шлем у входа"
    assert headset(client, creds["headsetId"])["label"] == "Шлем у входа"
    assert client.get("/api/stats").json()["headsets"][0]["label"] == "Шлем у входа"


def test_rename_validation(client):
    creds = register(client)
    assert client.patch(f"/api/headsets/{creds['headsetId']}", json={"label": "   "}).status_code == 422
    assert client.patch(f"/api/headsets/{creds['headsetId']}", json={"label": "x" * 65}).status_code == 422
    assert client.patch("/api/headsets/unknown", json={"label": "Шлем"}).status_code == 404
