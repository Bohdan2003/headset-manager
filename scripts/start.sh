#!/usr/bin/env bash
# Запуск сервера арены вместе с дашбордом.
#
#   ./scripts/start.sh
#
# - при первом запуске создаёт server/.env с админским токеном (HM_ADMIN_TOKEN);
# - собирает дашборд, если его ещё нет или исходники новее сборки;
# - запускает сервер: дашборд и API на http://<IP>:8000.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/server/.env"

say() { printf '\033[1m%s\033[0m\n' "$*"; }

# --- админский токен -------------------------------------------------------
if [[ -z "${HM_ADMIN_TOKEN:-}" ]] && ! grep -q '^HM_ADMIN_TOKEN=' "$ENV_FILE" 2>/dev/null; then
  say "Создаю server/.env с новым админским токеном (нужен для provision.sh)"
  umask 077
  echo "HM_ADMIN_TOKEN=$(openssl rand -hex 24)" >> "$ENV_FILE"
fi

# --- дашборд ---------------------------------------------------------------
cd "$ROOT/dashboard"
if [[ ! -d node_modules ]]; then
  say "Устанавливаю зависимости дашборда"
  npm install --no-audit --no-fund
fi
if [[ ! -f dist/index.html ]] || [[ -n "$(find src index.html package.json vite.config.ts -newer dist/index.html 2>/dev/null | head -1)" ]]; then
  say "Собираю дашборд"
  npm run build
fi

# --- сервер ----------------------------------------------------------------
IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}' || true)"
PORT="${HM_PORT:-8000}"
say "Дашборд: http://${IP:-localhost}:${PORT}   (остановить — Ctrl+C)"
say "Адрес сервера для provision.sh: http://${IP:-<IP>}:${PORT}"

cd "$ROOT/server"
exec uv run headset-server
