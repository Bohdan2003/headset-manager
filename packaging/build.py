"""
Build the Arena program: python packaging/build.py

Mac: dist/Arena.app. Windows: folder dist/Arena with Arena.exe (a folder, not one file: a single .exe
unpacks itself into a temporary folder on every start, and the adb server would then run from there).

The agent comes from packaging/prebuilt/agent.apk. On the Mac the file is updated on every build.
On Windows and in GitHub Actions (ARENA_PREBUILT_AGENT=1) it is used as is: the agent must always be
signed with the same key, otherwise installed agents can't be updated.

On the Mac, set JAVA_HOME to JDK 17. The agent is built before the old build/ and dist/ are deleted,
so a wrong Java or a failed agent build keeps the old program.
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server"
WORK = ROOT / "build"
PREBUILT = ROOT / "packaging" / "prebuilt"
SEP = ";" if sys.platform == "win32" else ":"
WINDOWS_ADB = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"

# Android Gradle plugin 8.7 needs Java 17 or newer, Gradle 8.10 runs on Java 23 or older
JAVA_MIN, JAVA_MAX = 17, 23

sys.path.insert(0, str(SERVER / "src"))


def run(cmd: list[str], cwd: Path) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True, shell=sys.platform == "win32")


def check_java() -> None:
    """Look at the same Java that gradlew takes: JAVA_HOME, else `java` from PATH."""
    home = os.environ.get("JAVA_HOME")
    java = str(Path(home) / "bin" / "java") if home else "java"
    try:
        r = subprocess.run([java, "-version"], capture_output=True, text=True)
    except OSError as e:
        raise SystemExit(f"Java not found ({java}): set JAVA_HOME to JDK 17") from e
    found = re.search(r'version "(\d+)', r.stderr + r.stdout)  # java prints the version to stderr
    if r.returncode != 0 or not found:
        raise SystemExit(f"Can't read the Java version ({java}): set JAVA_HOME to JDK 17")
    if not JAVA_MIN <= int(found[1]) <= JAVA_MAX:
        raise SystemExit(
            f"Java {found[1]} can't build the agent: set JAVA_HOME to JDK 17, "
            "for example JAVA_HOME=/opt/homebrew/opt/openjdk@17"
        )


def build_agent() -> None:
    """Only on the Mac: the agent signing key is there."""
    from headset_server.paths import read_gradle_version

    run(["./gradlew", "assembleDebug", "-q"], ROOT / "agent")
    PREBUILT.mkdir(exist_ok=True)
    shutil.copy(ROOT / "agent/app/build/outputs/apk/debug/app-debug.apk", PREBUILT / "agent.apk")
    name, code = read_gradle_version(ROOT / "agent/app/build.gradle.kts")
    (PREBUILT / "version.json").write_text(json.dumps({"name": name, "code": code}), encoding="utf-8")


def check_prebuilt_agent() -> None:
    """The ready APK must have the same version as the code, otherwise the program gets an old agent."""
    from headset_server.paths import read_gradle_version

    if not (PREBUILT / "agent.apk").exists():
        raise SystemExit("packaging/prebuilt/agent.apk is missing: build on the Mac first")
    name, code = read_gradle_version(ROOT / "agent/app/build.gradle.kts")
    built = json.loads((PREBUILT / "version.json").read_text(encoding="utf-8"))
    if (built["name"], built["code"]) != (name, code):
        raise SystemExit(
            f"packaging/prebuilt/agent.apk is {built['name']}, the code is {name}: rebuild it on the Mac"
        )


def collect_adb(target: Path) -> None:
    target.mkdir(parents=True)
    if sys.platform == "win32":
        with urllib.request.urlopen(WINDOWS_ADB) as r, zipfile.ZipFile(io.BytesIO(r.read())) as z:
            for name in ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll"):
                (target / name).write_bytes(z.read(f"platform-tools/{name}"))
    else:
        adb = shutil.which("adb")
        if adb is None:
            raise SystemExit("adb not found")
        shutil.copy(Path(adb).resolve(), target / "adb")


def main() -> None:
    if sys.platform == "darwin" and not os.environ.get("ARENA_PREBUILT_AGENT"):
        check_java()
        build_agent()
    check_prebuilt_agent()

    # Only now: if something above fails, the old program is still there
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.rmtree(ROOT / "dist", ignore_errors=True)
    resources = WORK / "resources"

    run(["npm", "ci", "--no-audit", "--no-fund"], ROOT / "dashboard")
    run(["npm", "run", "build"], ROOT / "dashboard")

    collect_adb(resources / "adb")
    shutil.copytree(PREBUILT, resources / "agent")

    run(
        [
            "uv", "run", "pyinstaller", "--noconfirm", "--windowed", "--name", "Arena",
            "--osx-bundle-identifier", "com.arena.server",
            "--distpath", str(ROOT / "dist"), "--workpath", str(WORK / "pyi"), "--specpath", str(WORK),
            "--paths", str(SERVER / "src"),
            "--add-data", f"{ROOT / 'dashboard' / 'dist'}{SEP}dashboard",
            "--add-data", f"{resources / 'agent'}{SEP}agent",
            "--add-binary", f"{resources / 'adb'}{SEP}adb",
            "--add-data", f"{SERVER / 'src/headset_server/migrations'}{SEP}headset_server/migrations",
            "--hidden-import", "aiosqlite",
            "--hidden-import", "sqlalchemy.dialects.sqlite.aiosqlite",
            "--hidden-import", "headset_server.db",
            "--collect-submodules", "alembic",
            "--collect-data", "alembic",
            "--collect-submodules", "uvicorn",
            str(ROOT / "packaging" / "arena_main.py"),
        ],
        SERVER,
    )
    print("Built:", "dist/Arena/Arena.exe" if sys.platform == "win32" else "dist/Arena.app")


if __name__ == "__main__":
    main()
