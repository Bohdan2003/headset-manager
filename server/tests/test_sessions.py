import json
import time
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from headset_server import create_app
from headset_server.db import Event, GameSession
from .conftest import heartbeat, hello, register

GAME = "com.Anvio.CityZ"
OTHER = "com.beatgames.beatsaber"
SHELL = "com.oculus.vrshell"


@pytest.fixture
def settings(settings):
    settings.session_grace_s = 1
    return settings


def sessions(client):
    async def load():
        async with client.app.state.session_factory() as s:
            from sqlalchemy import select

            return (await s.execute(select(GameSession).order_by(GameSession.id))).scalars().all()

    return client.portal.call(load)


class Agent:
    def __init__(self, client, creds):
        self._cm = client.websocket_connect("/agent")
        self.ws = self._cm.__enter__()
        self.ws.send_text(hello(creds))
        self.ws.receive_json()

    def app(self, pkg):
        self.ws.send_text(heartbeat(current_pkg=pkg))
        time.sleep(0.15)

    def send(self, msg):
        self.ws.send_text(json.dumps(msg))
        time.sleep(0.15)

    def idle_in(self, pkg, seconds):
        """Стоять в приложении pkg, продолжая слать heartbeat (иначе шлем уйдёт в офлайн)."""
        end = time.time() + seconds
        while time.time() < end:
            self.app(pkg)
            time.sleep(0.3)

    def close(self):
        self._cm.__exit__(None, None, None)


def wait_for(fn, timeout=3.0):
    """Сервер обрабатывает отключение асинхронно — ждём результата, а не фиксированную паузу."""
    end = time.time() + timeout
    while True:
        value = fn()
        if value or time.time() > end:
            return value
        time.sleep(0.1)


def test_short_exit_keeps_one_session_long_exit_ends_it(client):
    agent = Agent(client, register(client))
    agent.app(GAME)
    agent.app(SHELL)   # выглянул в меню Meta
    agent.app(GAME)    # вернулся быстрее grace
    [s] = sessions(client)
    assert (s.package, s.ended_at, s.exits) == (GAME, None, 1)

    agent.idle_in(SHELL, 2.5)  # grace=1 с, проверка раз в секунду
    [s] = sessions(client)
    assert s.end_reason == "exited"
    assert s.exits == 1  # последний выход — конец сессии, не «выход с возвратом»
    agent.close()


def test_switch_to_other_game_starts_new_session(client):
    agent = Agent(client, register(client))
    agent.app(GAME)
    agent.app(OTHER)
    a, b = sessions(client)
    assert (a.package, a.end_reason) == (GAME, "switched")
    assert (b.package, b.ended_at) == (OTHER, None)
    agent.close()


def test_guard_return_counted(client):
    agent = Agent(client, register(client))
    agent.app(GAME)
    agent.app(SHELL)
    agent.send({"type": "event", "kind": "guard_relaunch", "payload": {"pkg": GAME}})
    agent.app(GAME)
    [s] = sessions(client)
    assert (s.exits, s.guard_returns) == (1, 1)
    agent.close()


def test_operator_close_ends_session_and_stale_heartbeat_does_not_reopen(client):
    creds = register(client)
    agent = Agent(client, creds)
    agent.app(GAME)
    [cmd] = client.post(
        "/api/commands", json={"headsetIds": [creds["headsetId"]], "cmd": "close_game", "params": {}, "ttlS": 10}
    ).json()
    agent.ws.receive_json()
    agent.send({"type": "ack", "id": cmd["id"], "ok": True})
    agent.app(GAME)  # агент ещё не успел заметить, что игра закрыта
    [s] = sessions(client)
    assert s.end_reason == "closed"
    agent.close()


def test_disconnect_ends_session(client):
    agent = Agent(client, register(client))
    agent.app(GAME)
    agent.close()
    s = wait_for(lambda: next((x for x in sessions(client) if x.end_reason), None))
    assert s is not None and s.end_reason == "offline"


def test_open_session_closed_after_server_restart(settings):
    with TestClient(create_app(settings)) as c:
        creds = register(c)
        agent = Agent(c, creds)
        agent.app(GAME)
        # сервер «падает»: сессия остаётся открытой в БД
        c.app.state.sessions._active.clear()
        agent.close()
    with TestClient(create_app(settings)) as c:
        [s] = sessions(c)
        assert s.end_reason == "server_restart"
        assert s.ended_at is not None


def test_stats_aggregation(client):
    creds = register(client)
    hid = creds["headsetId"]
    now = datetime.now(UTC)
    t0 = now - timedelta(hours=1)

    async def seed():
        async with client.app.state.session_factory() as s:
            s.add_all([
                GameSession(headset_id=hid, package=GAME, started_at=t0, ended_at=t0 + timedelta(minutes=20),
                            end_reason="exited", exits=2, guard_returns=1),
                GameSession(headset_id=hid, package=GAME, started_at=t0 + timedelta(minutes=25),
                            ended_at=t0 + timedelta(minutes=35), end_reason="closed", exits=0, guard_returns=0),
                GameSession(headset_id=hid, package=OTHER, started_at=t0 + timedelta(minutes=40),
                            ended_at=None, exits=0, guard_returns=0),  # идёт до сих пор
                # батарея: 90 → 80 за 20 минут без зарядки = 30 %/ч; скачок через 2 часа не считаем
                Event(headset_id=hid, ts=t0, type="battery", payload={"level": 90, "charging": False}),
                Event(headset_id=hid, ts=t0 + timedelta(minutes=10), type="battery", payload={"level": 85, "charging": False}),
                Event(headset_id=hid, ts=t0 + timedelta(minutes=20), type="battery", payload={"level": 80, "charging": False}),
                Event(headset_id=hid, ts=t0 + timedelta(minutes=25), type="battery", payload={"level": 82, "charging": True}),
                Event(headset_id=hid, ts=t0 + timedelta(minutes=5), type="disconnect", payload={"reason": "timeout", "screenOn": True}),
                Event(headset_id=hid, ts=t0 + timedelta(minutes=6), type="disconnect", payload={"reason": "server_shutdown"}),
            ])
            await s.commit()

    client.portal.call(seed)
    st = client.get("/api/stats", params={"period": "7d"}).json()

    city, beat = st["games"]
    assert city["package"] == GAME
    assert city["playS"] == 30 * 60
    assert (city["sessions"], city["exits"], city["guardReturns"]) == (2, 2, 1)
    assert (city["endedByPlayer"], city["endedByOperator"]) == (1, 1)
    assert city["avgSessionS"] == 15 * 60
    assert beat["package"] == OTHER and abs(beat["playS"] - 20 * 60) < 5  # открытая — до текущего момента

    [h] = st["headsets"]
    assert h["disconnects"] == 1  # плановое отключение сервера — не обрыв
    assert h["batteryDrainPerHour"] == 30.0
    assert h["batteryLifeH"] == 3.3
    assert st["totals"]["sessions"] == 3
    assert len(st["days"]) == 7
    assert sum(d["playS"] for d in st["days"]) == st["totals"]["playS"]


def test_stats_empty(client):
    st = client.get("/api/stats").json()
    assert st["period"] == "today"
    assert st["totals"] == {"playS": 0, "sessions": 0, "exits": 0, "guardReturns": 0}
    assert len(st["days"]) == 1


def test_restart_game_starts_new_session_right_away(client):
    creds = register(client)
    agent = Agent(client, creds)
    agent.app(GAME)
    agent.app(SHELL)  # игру остановили, шлем на мгновение показал меню Meta
    [cmd] = client.post(
        "/api/commands", json={"headsetIds": [creds["headsetId"]], "cmd": "restart_game", "params": {}, "ttlS": 10}
    ).json()
    agent.ws.receive_json()
    agent.send({"type": "ack", "id": cmd["id"], "ok": True})
    agent.app(GAME)
    a, b = sessions(client)
    assert (a.end_reason, a.exits) == ("restarted", 0)  # служебный выход не считается выходом игрока
    assert (b.package, b.ended_at) == (GAME, None)
    agent.close()


def test_power_restart_starts_new_session(client):
    agent = Agent(client, register(client))
    agent.app(GAME)
    agent.app(SHELL)
    agent.send({"type": "event", "kind": "power_restart", "payload": {"pkg": GAME}})
    agent.app(GAME)
    a, b = sessions(client)
    assert (a.end_reason, a.exits) == ("power_button", 0)
    assert (b.package, b.ended_at) == (GAME, None)
    agent.close()


def test_reliability_stats_ignore_sleep_and_planned_shutdowns(client):
    creds = register(client)
    hid = creds["headsetId"]
    t0 = datetime.now(UTC) - timedelta(hours=1)

    async def seed():
        async with client.app.state.session_factory() as s:
            s.add_all([
                Event(headset_id=hid, ts=t0, type="disconnect", payload={"reason": "dropped", "screenOn": True}),
                Event(headset_id=hid, ts=t0, type="disconnect", payload={"reason": "timeout", "screenOn": True}),
                Event(headset_id=hid, ts=t0, type="disconnect", payload={"reason": "asleep", "screenOn": False}),
                Event(headset_id=hid, ts=t0, type="disconnect", payload={"reason": "closed", "screenOn": True}),
                # старая запись: сон от обрыва не отличить
                Event(headset_id=hid, ts=t0, type="disconnect", payload={"reason": "timeout"}),
                Event(headset_id=hid, ts=t0, type="charging", payload={"charging": False, "level": 60}),
                Event(headset_id=hid, ts=t0, type="charging", payload={"charging": False, "level": 100}),
                Event(headset_id=hid, ts=t0, type="charging", payload={"charging": True, "level": 60}),
                # разряд во сне не должен попасть в оценку времени работы
                Event(headset_id=hid, ts=t0, type="battery", payload={"level": 90, "charging": False, "screenOn": False}),
                Event(headset_id=hid, ts=t0 + timedelta(minutes=20), type="battery",
                      payload={"level": 89, "charging": False, "screenOn": False}),
            ])
            await s.commit()

    client.portal.call(seed)
    [h] = client.get("/api/stats", params={"period": "7d"}).json()["headsets"]
    assert h["disconnects"] == 2
    assert h["chargeInterruptions"] == 1
    assert h["batteryLifeH"] is None


def test_asleep_headset_dropping_off_is_not_a_drop(client):
    creds = register(client)
    with client.websocket_connect("/agent") as ws:
        ws.send_text(hello(creds))
        ws.receive_json()
        hb = json.loads(heartbeat())
        hb["screenOn"] = False
        ws.send_text(json.dumps(hb))
        time.sleep(2.5)  # offline_after_s=1: сервер закрывает молчащий шлем

    async def reasons():
        async with client.app.state.session_factory() as s:
            from sqlalchemy import select

            rows = await s.execute(select(Event).where(Event.type == "disconnect"))
            return [e.payload["reason"] for e in rows.scalars()]

    assert client.portal.call(reasons) == ["asleep"]


def test_charging_change_is_logged(client):
    creds = register(client)
    agent = Agent(client, creds)

    def beat(charging):
        hb = json.loads(heartbeat(battery=70))
        hb["charging"] = charging
        agent.send(hb)

    beat(True)
    beat(False)
    [h] = client.get("/api/stats", params={"period": "7d"}).json()["headsets"]
    assert h["chargeInterruptions"] == 1
    agent.close()
