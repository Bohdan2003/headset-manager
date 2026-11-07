import json
import time

from headset_server import commands as commands_module

from .conftest import heartbeat, hello, register


def connect_agent(client, creds):
    ws = client.websocket_connect("/agent")
    agent = ws.__enter__()
    agent.send_text(hello(creds))
    assert agent.receive_json()["type"] == "welcome"
    return ws, agent


def post(client, ids, cmd, params=None, ttl_s=10):
    return client.post("/api/commands", json={"headsetIds": ids, "cmd": cmd, "params": params or {}, "ttlS": ttl_s})


def test_command_reaches_agent_and_ack_marks_it_done(client):
    creds = register(client)
    ws, agent = connect_agent(client, creds)
    try:
        with client.websocket_connect("/live") as live:
            live.receive_json()  # snapshot

            r = post(client, [creds["headsetId"]], "launch", {"pkg": "com.Anvio.CityZ", "guard": True})
            assert r.status_code == 200
            [cmd] = r.json()
            assert cmd["status"] == "sent"

            got = agent.receive_json()
            assert got == {
                "type": "command", "id": cmd["id"], "cmd": "launch",
                "params": {"pkg": "com.Anvio.CityZ", "guard": True}, "ttlS": 10,
            }
            assert live.receive_json()["command"]["status"] == "sent"

            agent.send_text(json.dumps({"type": "ack", "id": cmd["id"], "ok": True}))
            update = live.receive_json()
            assert update["type"] == "command"
            assert update["command"]["status"] == "acked"
            assert update["command"]["ackedAt"] is not None
    finally:
        ws.__exit__(None, None, None)


def test_failed_ack_keeps_reason(client):
    creds = register(client)
    ws, agent = connect_agent(client, creds)
    try:
        with client.websocket_connect("/live") as live:
            live.receive_json()
            [cmd] = post(client, [creds["headsetId"]], "reboot").json()
            agent.receive_json()
            live.receive_json()
            agent.send_text(json.dumps({"type": "ack", "id": cmd["id"], "ok": False, "reason": "no_adb"}))
            update = live.receive_json()["command"]
            assert (update["status"], update["reason"]) == ("failed", "no_adb")
    finally:
        ws.__exit__(None, None, None)


def test_offline_headset_fails_immediately(client):
    creds = register(client)
    [cmd] = post(client, [creds["headsetId"]], "show_menu").json()
    assert (cmd["status"], cmd["reason"]) == ("failed", "offline")


def test_one_command_many_headsets(client):
    a, b = register(client, "S-A", "Шлем A"), register(client, "S-B", "Шлем B")
    ws, agent = connect_agent(client, a)
    try:
        result = post(client, [a["headsetId"], b["headsetId"], "unknown-id"], "set_sleep", {"disabled": True}).json()
        by_id = {c["headsetId"]: c for c in result}
        assert set(by_id) == {a["headsetId"], b["headsetId"]}  # неизвестный шлем пропущен
        assert by_id[a["headsetId"]]["status"] == "sent"
        assert by_id[b["headsetId"]]["reason"] == "offline"
        assert agent.receive_json()["params"] == {"disabled": True}
    finally:
        ws.__exit__(None, None, None)


def test_no_ack_becomes_timeout(client, monkeypatch):
    monkeypatch.setattr(commands_module, "ACK_GRACE_S", 0)
    creds = register(client)
    ws, agent = connect_agent(client, creds)
    try:
        with client.websocket_connect("/live") as live:
            live.receive_json()
            post(client, [creds["headsetId"]], "show_menu", ttl_s=1)
            agent.receive_json()
            assert live.receive_json()["command"]["status"] == "sent"
            for _ in range(5):  # heartbeat, чтобы шлем не ушёл в офлайн, пока ждём таймаут
                agent.send_text(heartbeat())
                time.sleep(0.5)
            for _ in range(20):  # среди обновлений шлема ищем сообщение о команде
                msg = live.receive_json()
                if msg["type"] == "command":
                    break
            assert (msg["command"]["status"], msg["command"]["reason"]) == ("timeout", "timeout")
    finally:
        ws.__exit__(None, None, None)


def test_bad_params_rejected_before_reaching_agent(client):
    creds = register(client)
    assert post(client, [creds["headsetId"]], "launch", {"pkg": "x; reboot"}).status_code == 422
    assert post(client, [creds["headsetId"]], "launch", {}).status_code == 422
    assert post(client, [creds["headsetId"]], "show_menu", {"extra": 1}).status_code == 422
    assert post(client, [creds["headsetId"]], "format_disk").status_code == 422
    assert post(client, [], "show_menu").status_code == 422


def test_apps_and_guard_from_agent_show_on_headset(client):
    creds = register(client)
    ws, agent = connect_agent(client, creds)
    try:
        agent.send_text(json.dumps({"type": "apps", "apps": [
            {"package": "com.beatgames.beatsaber", "title": "Beat Saber"},
            {"package": "com.Anvio.CityZ", "title": "City Z"},
        ]}))
        hb = json.loads(heartbeat())
        hb["guardPkg"] = "com.Anvio.CityZ"
        agent.send_text(json.dumps(hb))
        time.sleep(0.2)
        [h] = client.get("/api/headsets").json()
        assert [a["title"] for a in h["apps"]] == ["Beat Saber", "City Z"]
        assert h["guardPkg"] == "com.Anvio.CityZ"
    finally:
        ws.__exit__(None, None, None)


def test_snapshot_includes_last_command(client):
    creds = register(client)
    [cmd] = post(client, [creds["headsetId"]], "show_menu").json()  # офлайн → failed сразу
    with client.websocket_connect("/live") as live:
        snap = live.receive_json()
        assert [(c["id"], c["status"]) for c in snap["commands"]] == [(cmd["id"], "failed")]


def test_close_game_params(client):
    creds = register(client)
    ws, agent = connect_agent(client, creds)
    try:
        assert post(client, [creds["headsetId"]], "close_game").status_code == 200
        assert agent.receive_json()["params"] == {"pkg": None}  # без pkg — закрыть текущее
        assert post(client, [creds["headsetId"]], "close_game", {"pkg": "com.Anvio.CityZ"}).status_code == 200
        assert agent.receive_json()["params"] == {"pkg": "com.Anvio.CityZ"}
        assert post(client, [creds["headsetId"]], "close_game", {"pkg": "a b"}).status_code == 422
    finally:
        ws.__exit__(None, None, None)


def test_app_vr_flag_survives_restart(settings):
    from fastapi.testclient import TestClient

    from headset_server import create_app

    with TestClient(create_app(settings)) as c:
        creds = register(c)
        ws, agent = connect_agent(c, creds)
        try:
            agent.send_text(json.dumps({"type": "apps", "apps": [
                {"package": "com.beatgames.beatsaber", "title": "Beat Saber", "vr": True},
                {"package": "com.whatsapp", "title": "WhatsApp", "vr": False},
            ]}))
            time.sleep(0.2)
        finally:
            ws.__exit__(None, None, None)
    with TestClient(create_app(settings)) as c:
        [h] = c.get("/api/headsets").json()
        assert {a["package"]: a["vr"] for a in h["apps"]} == {"com.beatgames.beatsaber": True, "com.whatsapp": False}


def test_guard_params(client):
    creds = register(client)
    ws, agent = connect_agent(client, creds)
    try:
        assert post(client, [creds["headsetId"]], "guard", {"current": True}).status_code == 200
        assert agent.receive_json()["params"] == {"pkg": None, "current": True}
        assert post(client, [creds["headsetId"]], "guard", {}).status_code == 200
        assert agent.receive_json()["params"] == {"pkg": None, "current": False}  # выключить
        r = post(client, [creds["headsetId"]], "guard", {"pkg": "com.Anvio.CityZ", "current": True})
        assert r.status_code == 422
    finally:
        ws.__exit__(None, None, None)


def test_power_commands_and_screen_state(client):
    creds = register(client)
    ws, agent = connect_agent(client, creds)
    try:
        for cmd in ("sleep", "power_off", "request_access"):
            assert post(client, [creds["headsetId"]], cmd).status_code == 200
            assert agent.receive_json()["cmd"] == cmd
        assert post(client, [creds["headsetId"]], "sleep", {"x": 1}).status_code == 422
        assert post(client, [creds["headsetId"]], "wake").status_code == 422
        hb = json.loads(heartbeat())
        hb["screenOn"] = False
        agent.send_text(json.dumps(hb))
        time.sleep(0.2)
        assert client.get("/api/headsets").json()[0]["screenOn"] is False
    finally:
        ws.__exit__(None, None, None)


def test_asleep_headset_refuses_commands_at_once(client):
    creds = register(client)
    ws, agent = connect_agent(client, creds)
    try:
        hb = json.loads(heartbeat())
        hb["screenOn"] = False
        agent.send_text(json.dumps(hb))
        time.sleep(0.2)
        [cmd] = post(client, [creds["headsetId"]], "launch", {"pkg": "com.Anvio.CityZ"}).json()
        assert (cmd["status"], cmd["reason"]) == ("failed", "asleep")

        hb["screenOn"] = True  # проснулся — команды снова идут
        agent.send_text(json.dumps(hb))
        time.sleep(0.2)
        [cmd] = post(client, [creds["headsetId"]], "launch", {"pkg": "com.Anvio.CityZ"}).json()
        assert cmd["status"] == "sent"
        assert agent.receive_json()["cmd"] == "launch"
    finally:
        ws.__exit__(None, None, None)
