"""
Эмулятор агента: изображает один или несколько шлемов, чтобы разрабатывать дашборд без настоящего шлема.

    uv run python tools/fake_agent.py --count 3

Сам регистрирует шлемы «Fake 01..N» (нужен HM_ADMIN_TOKEN), шлёт heartbeat раз в 5 с:
батарея медленно садится, иногда шлем «пропадает» и переподключается.
Выполняет команды как настоящий агент: launch, show_menu, set_sleep, guard;
команды через ADB отклоняет (no_adb), если ADB «не готов», иначе выполняет.
"""

import argparse
import asyncio
import json
import os
import random

import httpx
import websockets

APPS = [
    {"package": "com.Anvio.CityZ", "title": "City Z", "vr": True},
    {"package": "com.beatgames.beatsaber", "title": "Beat Saber", "vr": True},
    {"package": "com.Warpfrog.BladeAndSorcery", "title": "Blade & Sorcery", "vr": True},
    {"package": "com.Anvio.SciFi", "title": "Sci-Fi", "vr": True},
    {"package": "com.whatsapp", "title": "WhatsApp", "vr": False},
    {"package": "com.oculus.browser", "title": "Browser", "vr": False},
]
MENU = "com.arena.agent"
ADB = ["ready", "ready", "ready", "waiting_confirmation"]


async def register(server: str, admin_token: str, n: int) -> dict:
    async with httpx.AsyncClient() as http:
        r = await http.post(
            f"{server}/api/headsets",
            json={"label": f"Fake {n:02d}", "serial": f"FAKE-{n:04d}"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        r.raise_for_status()
        return r.json()


async def run_headset(server: str, creds: dict, n: int, interval: float) -> None:
    ws_url = server.replace("http", "ws", 1) + "/agent"
    st = {
        "battery": random.randint(40, 100),
        "app": random.choice([a["package"] for a in APPS] + ["com.oculus.vrshell"]),
        "adb": random.choice(ADB),
        "sleep_disabled": True,
        "guard": None,
        "screen_on": True,
        "left": random.randint(10, 100),
        "right": random.randint(10, 100),
        "left_on": random.random() > 0.3,
    }

    def heartbeat() -> str:
        return json.dumps({
            "type": "heartbeat", "battery": st["battery"], "charging": n % 2 == 1,
            "temp": round(random.uniform(28, 36), 1), "currentPkg": st["app"],
            "adb": st["adb"], "sleepDisabled": st["sleep_disabled"], "guardPkg": st["guard"], "screenOn": st["screen_on"],
            "controllers": [
                {"side": "left", "battery": st["left"], "connected": st["left_on"]},
                {"side": "right", "battery": st["right"], "connected": True},
            ],
        })

    def execute(cmd: dict) -> dict:
        name, p = cmd["cmd"], cmd["params"]
        ack = {"type": "ack", "id": cmd["id"], "ok": True}
        if name == "launch":
            st["app"] = p["pkg"]
            st["guard"] = p["pkg"] if p.get("guard") else None
        elif name == "show_menu":
            st["app"], st["guard"] = MENU, None
        elif name == "set_sleep":
            st["sleep_disabled"] = p["disabled"]
        elif name == "guard":
            game = st["app"] if st["app"] in [a["package"] for a in APPS] else None
            st["guard"] = p.get("pkg") or (game if p.get("current") else None)
        elif name == "request_access":
            st["adb"] = "ready"  # как будто оператор сразу подтвердил в шлеме
        elif name in ("close_game", "restart_game", "reboot", "sleep", "power_off"):
            if st["adb"] != "ready":
                return {**ack, "ok": False, "reason": "no_adb"}
            if name == "sleep":
                st["screen_on"] = False
            elif name == "power_off":
                pass  # эмулятор продолжает работать
            elif name == "restart_game":
                pass  # игра и охрана остаются прежними
            elif name == "close_game":
                st["app"], st["guard"] = MENU, None  # как настоящий агент: после закрытия — наше меню
            else:
                st["app"], st["guard"] = "com.oculus.vrshell", None
        print(f"[{n:02d}] {name} {p} -> {'ok' if ack['ok'] else ack}", flush=True)
        return ack

    async def reader(ws) -> None:
        async for raw in ws:
            msg = json.loads(raw)
            if msg.get("type") == "command":
                await asyncio.sleep(random.uniform(0.2, 1.0))  # как будто выполняем
                await ws.send(json.dumps(execute(msg)))
                await ws.send(heartbeat())  # состояние изменилось — сообщить сразу

    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps({
                    "type": "hello", "headsetId": creds["headsetId"],
                    "token": creds["token"], "agentVersion": "fake-0.2",
                }))
                print(f"[{n:02d}] connected: {await ws.recv()}", flush=True)
                await ws.send(json.dumps({"type": "apps", "apps": APPS}))
                read = asyncio.create_task(reader(ws))
                try:
                    while True:
                        st["battery"] = max(5, st["battery"] - random.choice([0, 0, 1]))
                        await ws.send(heartbeat())
                        if random.random() < 0.01:
                            print(f"[{n:02d}] simulating Wi-Fi drop", flush=True)
                            break
                        await asyncio.sleep(interval)
                finally:
                    read.cancel()
        except (OSError, websockets.ConnectionClosed) as e:
            print(f"[{n:02d}] connection lost: {e}", flush=True)
        await asyncio.sleep(random.uniform(1, 5))


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="http://localhost:8000")
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--interval", type=float, default=5.0)
    args = p.parse_args()

    admin_token = os.environ.get("HM_ADMIN_TOKEN")
    if not admin_token:
        raise SystemExit("set HM_ADMIN_TOKEN (the same as the server's)")

    creds = [await register(args.server, admin_token, n) for n in range(1, args.count + 1)]
    await asyncio.gather(*(run_headset(args.server, c, n, args.interval) for n, c in enumerate(creds, 1)))


if __name__ == "__main__":
    asyncio.run(main())
