"""
Программа «в один клик»: поднимает сервер, открывает дашборд, показывает маленькое окно
с адресом и кнопками. Закрытие окна останавливает сервер.
"""

import logging
import multiprocessing
import secrets
import socket
import threading
import tkinter as tk
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path
from tkinter import messagebox

import uvicorn

from . import create_app, paths, setup_tools
from .auth import Auth
from .config import Settings

PORT = 8000


def admin_token(data: Path) -> str:
    """Токен создаётся при первом запуске и хранится рядом с базой."""
    path = data / "admin-token.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    token = secrets.token_hex(24)
    path.touch(mode=0o600)
    path.write_text(token, encoding="utf-8")
    return token


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main() -> None:
    multiprocessing.freeze_support()
    data = paths.data_dir()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[RotatingFileHandler(data / "arena.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")],
    )
    local_url = f"http://localhost:{PORT}"

    root = tk.Tk()
    root.title("Arena")
    root.resizable(False, False)

    if port_busy(PORT):
        root.withdraw()
        messagebox.showinfo("Arena", "Arena is already running. Opening the dashboard.")
        webbrowser.open(local_url)
        return

    settings = Settings(
        _env_file=None,
        admin_token=admin_token(data),
        database_url=f"sqlite+aiosqlite:///{data / 'headsets.db'}",
        dashboard_dir=str(paths.dashboard_dir()),
        auth_file=str(data / "auth.json"),
        port=PORT,
    )
    # log_config=None: у программы без консоли нет stdout, логи идут в arena.log
    server = uvicorn.Server(
        uvicorn.Config(create_app(settings), host=settings.host, port=PORT, workers=1, log_config=None)
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        network_url = setup_tools.local_server_url(PORT)
    except OSError:
        network_url = "no network"

    status = tk.StringVar(value="Starting…")
    frame = tk.Frame(root, padx=24, pady=20)
    frame.pack()
    tk.Label(frame, text="Arena server", font=("", 16, "bold")).pack(anchor="w")
    tk.Label(frame, textvariable=status).pack(anchor="w", pady=(4, 0))
    tk.Label(frame, text=f"Network address: {network_url}", fg="#555").pack(anchor="w", pady=(0, 14))
    buttons = tk.Frame(frame)
    buttons.pack(anchor="w")

    def stop() -> None:
        status.set("Stopping…")
        root.update()
        server.should_exit = True
        thread.join(timeout=10)
        root.destroy()

    tk.Button(buttons, text="Open dashboard", command=lambda: webbrowser.open(local_url)).pack(side="left")
    tk.Button(buttons, text="Stop", command=stop).pack(side="left", padx=(8, 0))

    def reset_password() -> None:
        if messagebox.askyesno("Arena", "Reset the dashboard password? Everyone will be signed out."):
            Auth(data / "auth.json").reset()
            webbrowser.open(local_url)

    tk.Button(buttons, text="Reset password", command=reset_password).pack(side="left", padx=(8, 0))
    root.protocol("WM_DELETE_WINDOW", stop)

    opened = {"done": False}

    def watch() -> None:
        if server.started:
            status.set("Running")
            if not opened["done"]:
                opened["done"] = True
                webbrowser.open(local_url)
        elif not thread.is_alive():
            status.set(f"Failed to start. See {data / 'arena.log'}")
            return
        root.after(500, watch)

    watch()
    root.mainloop()
