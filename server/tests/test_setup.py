import hashlib
import json
import stat
import sys
import time

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from headset_server import api, create_app, paths, setup_tools

from .conftest import hello, register

FAKE_ADB = r"""#!{python}
import json, os, sys
state_path = {state!r}
state = json.load(open(state_path))
args = sys.argv[1:]
state["calls"].append(args)
if args[:1] == ["-s"]:
    args = args[2:]
out, code = "", 0
if args[:1] == ["devices"]:
    out = "List of devices attached\n" + "".join(f"{{d}} {{s}} usb:1 model:Quest_2\n" for d, s in state["devices"].items())
elif args[:1] == ["keygen"]:
    open(args[1], "w").write(state["pem"])
    open(args[1] + ".pub", "w").write("QAAAAFAKEKEYFAKEKEYFAKEKEYFAKEKEYFAKEKEYFAKE user@host\n")
elif args[:1] == ["get-state"]:
    out = "device"
elif args[:1] == ["logcat"]:
    allow = "true" if state["always_allow"] else "false"
    out = f"D/AdbDebuggingManager: Logging key QAAAAFAKEKEYFAKEKEYFAKEKEYFAKEKEYFAKEKEYFAKE u@h, state = 2, alwaysAllow = {{allow}}"
elif args[:1] == ["install"]:
    state["installed"] = state["apk_code"]
    if state.get("install_error"):
        out, code = state["install_error"], 1
elif args[:1] == ["uninstall"]:
    state["installed"] = None
    out = "Success"
elif args[:1] == ["shell"]:
    cmd = " ".join(args[1:])
    if cmd == "getprop ro.serialno":
        out = "SER-1"
    elif cmd == "getprop ro.product.model":
        out = "Quest 2"
    elif cmd.startswith("dumpsys package"):
        if state["installed"]:
            out = f"versionCode={{state['installed']}} minSdk=29\nversionName=0.{{state['installed']}}\n"
            out += "android.permission.WRITE_SECURE_SETTINGS: granted=true\nandroid.permission.DUMP: granted=true\n"
    elif cmd.startswith("settings get secure enabled_accessibility_services"):
        out = state["a11y"]
    elif cmd.startswith("settings put secure enabled_accessibility_services"):
        state["a11y"] = cmd.split()[-1]
    elif "PROVISION_PING" in cmd:
        out = 'Broadcast completed: result=0, data="ok android_id=abc123"'
    elif "PROVISION" in cmd:
        state["provisioned"].append(cmd)
        out = 'Broadcast completed: result=0, data="ok android_id=abc123"'
json.dump(state, open(state_path, "w"))
print(out)
sys.exit(code)
"""


@pytest.fixture
def adb(tmp_path, monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    state_file = tmp_path / "adb.json"
    state = {
        "devices": {"SER-1": "device"}, "installed": None, "apk_code": 10, "a11y": "null",
        "provisioned": [], "calls": [], "always_allow": True, "pem": pem,
    }
    state_file.write_text(json.dumps(state))
    script = tmp_path / "adb"
    script.write_text(FAKE_ADB.format(python=sys.executable, state=str(state_file)))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(paths, "adb_path", lambda: str(script))
    monkeypatch.setattr(paths, "bundled_agent", lambda: ("0.10", 10))
    monkeypatch.setattr(setup_tools, "local_server_url", lambda port: f"http://10.0.0.5:{port}")

    class State:
        def __getitem__(self, k):
            return json.loads(state_file.read_text())[k]

        def set(self, **kw):
            data = json.loads(state_file.read_text())
            data.update(kw)
            state_file.write_text(json.dumps(data))

    return State()


def run(client, kind, label=None):
    r = client.post("/api/setup/jobs", json={"kind": kind, "adbId": "SER-1", "label": label})
    assert r.status_code == 200, r.text
    for _ in range(100):
        job = client.get("/api/setup").json()["job"]
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.1)
    raise AssertionError(f"job did not finish: {job}")


def device(client):
    return client.get("/api/setup").json()["devices"][0]


def test_setup_is_refused_from_the_network(settings, adb):
    with TestClient(create_app(settings), client=("192.168.50.20", 5000)) as c:
        assert c.get("/api/setup").status_code == 403
        assert c.post("/api/setup/jobs", json={"kind": "remove", "adbId": "SER-1"}).status_code == 403
        assert c.get("/api/headsets").status_code == 200  # остальное работает


def test_setup_allowed_on_server_computer_by_network_address():
    class Req:
        client = type("C", (), {"host": "192.168.50.74"})
        scope = {"server": ("192.168.50.74", 8000)}

    api.require_local(Req())  # не бросает исключение
    Req.client = type("C", (), {"host": "192.168.50.20"})
    with pytest.raises(HTTPException):
        api.require_local(Req())


def test_status_not_installed_outdated_current(client, adb):
    assert device(client)["status"] == "not_installed"
    adb.set(installed=9)
    d = device(client)
    assert (d["status"], d["installedVersion"]) == ("outdated", "0.9")
    adb.set(installed=10)
    assert device(client)["status"] == "current"
    adb.set(installed=11)
    assert device(client)["status"] == "newer"


def test_unauthorized_device_is_listed(client, adb):
    adb.set(devices={"SER-1": "unauthorized"})
    assert device(client)["status"] == "unauthorized"


def test_install_registers_headset_and_provisions_agent(client, adb):
    job = run(client, "install", "Шлем 05")
    assert job["status"] == "done", job
    [h] = client.get("/api/headsets").json()
    assert (h["label"], h["serial"]) == ("Шлем 05", "SER-1")
    server, key = adb["provisioned"]
    assert f"--es headset_id {h['id']}" in server and "http://10.0.0.5:8000" in server
    assert "key_b64" in key and "cert_b64" in key
    assert adb["a11y"] == setup_tools.A11Y
    d = device(client)
    assert (d["status"], d["label"], d["permissionsOk"]) == ("current", "Шлем 05", True)
    assert any(c == ["kill-server"] for c in adb["calls"])  # adb-сервер возвращён к ключу компьютера


def test_install_keeps_other_accessibility_services(client, adb):
    adb.set(a11y="com.other/.Service")
    run(client, "install", "Шлем")
    assert adb["a11y"] == f"com.other/.Service:{setup_tools.A11Y}"


def test_install_stops_if_always_allow_not_ticked(client, adb):
    adb.set(always_allow=False)
    job = run(client, "install", "Шлем")
    assert job["status"] == "failed"
    assert "Always allow" in job["error"]
    assert len(adb["provisioned"]) == 1  # ключ агенту не передан


def test_install_needs_cable_and_name(client, adb):
    assert run(client, "install", None)["error"] == "headset name is required"
    r = client.post("/api/setup/jobs", json={"kind": "install", "adbId": "192.168.1.5:5555", "label": "x"})
    assert r.status_code == 200
    for _ in range(50):
        job = client.get("/api/setup").json()["job"]
        if job["status"] == "failed":
            break
        time.sleep(0.1)
    assert "USB" in job["error"]


def test_update_keeps_registration(client, adb):
    adb.set(installed=9)
    assert run(client, "update")["status"] == "done"
    assert device(client)["status"] == "current"
    assert adb["provisioned"] == []  # ключ и токен не трогаем


def test_incompatible_signature_is_explained(client, adb):
    adb.set(install_error="Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures do not match]", installed=9)
    assert "Remove it first" in run(client, "update")["error"]


def test_remove_restores_power_settings(client, adb):
    adb.set(installed=10)
    assert run(client, "remove")["status"] == "done"
    assert device(client)["status"] == "not_installed"
    calls = [" ".join(c) for c in adb["calls"]]
    assert any("settings delete global power_button_long_press" in c for c in calls)
    assert any("automation_disable" in c for c in calls)


def test_only_one_job_at_a_time(client, adb):
    jobs = client.app.state.setup_jobs
    jobs.current = setup_tools.SetupJob(id="x", kind="update", adb_id="SER-1", status="running")
    r = client.post("/api/setup/jobs", json={"kind": "remove", "adbId": "SER-1"})
    assert r.status_code == 409


def test_certificate_matches_adb_format(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path = tmp_path / "adbkey"
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ))
    key_der, cert_der = setup_tools._key_and_cert(path)
    cert = x509.load_der_x509_certificate(cert_der)
    assert cert.subject.rfc4514_string() == "CN=Adb,O=Android,C=US"
    assert cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is True
    assert cert.public_key().public_numbers() == key.public_key().public_numbers()
    assert serialization.load_der_private_key(key_der, None).key_size == 2048


@pytest.mark.parametrize(
    ("installed", "status"),
    [
        ("0.11.2", "current"), ("0.11.3", "newer"), ("0.11.2-x", "unknown"), (None, "unknown"),
        ("0.11.0", "needs_cable"),
    ],
)
def test_fleet_status(installed, status):
    assert setup_tools.fleet_status(installed, "0.11.2") == status


def test_fleet_status_outdated_after_first_wifi_capable_agent():
    assert setup_tools.fleet_status("0.11.2", "0.12.0") == "outdated"


def test_update_over_wifi_sends_command_with_checksum(client, adb, monkeypatch, tmp_path):
    apk = tmp_path / "agent.apk"
    apk.write_bytes(b"apk-bytes")
    monkeypatch.setattr(paths, "agent_apk", lambda: apk)
    creds = register(client)
    with client.websocket_connect("/agent") as ws:
        ws.send_text(hello(creds))
        ws.receive_json()
        r = client.post("/api/setup/update-wifi", json={"headsetIds": [creds["headsetId"]]})
        assert r.status_code == 200, r.text
        cmd = ws.receive_json()
        assert cmd["cmd"] == "update_agent"
        assert cmd["ttlS"] == 60
        assert cmd["params"] == {
            "versionCode": 10,
            "sha256": hashlib.sha256(b"apk-bytes").hexdigest(),
            "path": "/api/agent/apk",
        }
    assert client.get("/api/agent/apk").content == b"apk-bytes"


def test_update_cannot_be_sent_as_ordinary_command(client, adb):
    creds = register(client)
    r = client.post("/api/commands", json={
        "headsetIds": [creds["headsetId"]], "cmd": "update_agent",
        "params": {"versionCode": 1, "sha256": "0" * 64, "path": "/evil"},
    })
    assert r.status_code == 403


def test_wifi_update_refused_from_the_network(settings, adb):
    with TestClient(create_app(settings), client=("192.168.50.20", 5000)) as c:
        r = c.post("/api/setup/update-wifi", json={"headsetIds": ["x"]})
        assert r.status_code == 403


def test_fleet_listed_in_setup(client, adb):
    creds = register(client, "S-1", "Шлем 1")
    with client.websocket_connect("/agent") as ws:
        ws.send_text(hello(creds))  # agentVersion 0.0.1
        ws.receive_json()
        [f] = client.get("/api/setup").json()["fleet"]
        assert (f["label"], f["online"], f["agentVersion"]) == ("Шлем 1", True, "0.0.1")


def test_wifi_update_progress_reaches_dashboard(client, adb, monkeypatch, tmp_path):
    apk = tmp_path / "agent.apk"
    apk.write_bytes(b"apk")
    monkeypatch.setattr(paths, "agent_apk", lambda: apk)
    creds = register(client)
    hid = creds["headsetId"]

    def update():
        return client.get("/api/headsets").json()[0]["update"]

    with client.websocket_connect("/agent") as ws:
        ws.send_text(hello(creds))
        ws.receive_json()
        client.post("/api/setup/update-wifi", json={"headsetIds": [hid]})
        ws.receive_json()
        assert update()["stage"] == "starting"

        ws.send_text(json.dumps({"type": "event", "kind": "update_progress",
                                 "payload": {"stage": "downloading", "percent": 45}}))
        time.sleep(0.2)
        assert (update()["stage"], update()["percent"]) == ("downloading", 45)

        ws.send_text(json.dumps({"type": "event", "kind": "update_failed", "payload": {"reason": "no space"}}))
        time.sleep(0.2)
        assert (update()["stage"], update()["reason"]) == ("failed", "no space")

    with client.websocket_connect("/agent") as ws:  # перезапустившийся агент — обновление закончено
        ws.send_text(hello(creds))
        ws.receive_json()
        time.sleep(0.2)
        assert update() is None
