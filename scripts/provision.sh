#!/usr/bin/env bash
# Разовая настройка шлема по кабелю: ставит агента, выдаёт права, регистрирует шлем
# на сервере и передаёт агенту ключ ADB для «сильных» команд (вариант C).
#
#   ./scripts/provision.sh "Шлем 02"
#   ./scripts/provision.sh "Шлем 02" --server http://192.168.50.74:8000
#   ./scripts/provision.sh "Шлем 02" --no-key      # без ключа ADB (только вариант B)
#
# Нужно: шлем подключён кабелем и разрешил USB-отладку этому компьютеру; сервер запущен
# (scripts/start.sh); HM_ADMIN_TOKEN в окружении или в server/.env.
# Повторный запуск для того же шлема безопасен: запись на сервере сохраняется, токен новый.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APK="$ROOT/agent/app/build/outputs/apk/debug/app-debug.apk"
PKG="com.arena.agent"
A11Y="$PKG/$PKG.WatcherService"

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()   { printf '   \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '   \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\n\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# --- аргументы ---------------------------------------------------------------
LABEL="" SERVER="${HM_SERVER:-}" WITH_KEY=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --server) SERVER="$2"; shift 2 ;;
    --no-key) WITH_KEY=0; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) [[ -z "$LABEL" ]] && LABEL="$1" || die "лишний аргумент: $1"; shift ;;
  esac
done
[[ -n "$LABEL" ]] || die "укажите название шлема: ./scripts/provision.sh \"Шлем 02\""

if [[ -z "$SERVER" ]]; then
  IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
  [[ -n "$IP" ]] || die "не удалось определить IP компьютера — укажите --server http://<IP>:8000"
  SERVER="http://$IP:8000"
fi
SERVER="${SERVER%/}"

if [[ -z "${HM_ADMIN_TOKEN:-}" && -f "$ROOT/server/.env" ]]; then
  HM_ADMIN_TOKEN="$(grep '^HM_ADMIN_TOKEN=' "$ROOT/server/.env" | tail -1 | cut -d= -f2-)"
fi
[[ -n "${HM_ADMIN_TOKEN:-}" ]] || die "нет HM_ADMIN_TOKEN (запустите scripts/start.sh — он создаст server/.env)"

for tool in adb curl python3 openssl; do
  command -v "$tool" >/dev/null || die "не найден $tool"
done

json() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }

# --- 1. проверки ---------------------------------------------------------------
say "1. Проверки"
STATE="$(adb -d get-state 2>&1 || true)"
[[ "$STATE" == "device" ]] || die "шлем по кабелю не готов ($STATE). Подключите кабель, разрешите USB-отладку в шлеме"
SERIAL="$(adb -d shell getprop ro.serialno | tr -d '\r')"
ok "шлем $(adb -d shell getprop ro.product.model | tr -d '\r'), серийный номер $SERIAL"

curl -sf "$SERVER/health" >/dev/null || die "сервер $SERVER не отвечает (запущен scripts/start.sh?)"
HOSTPORT="${SERVER#*://}"
if adb -d shell "toybox nc -z -w 3 ${HOSTPORT%:*} ${HOSTPORT##*:}" 2>/dev/null; then
  ok "сервер $SERVER доступен и с компьютера, и со шлема"
else
  die "шлем не достаёт до $SERVER: шлем и компьютер в одной сети Wi-Fi? Брандмауэр пропускает порт?"
fi

# --- 2. агент ------------------------------------------------------------------
say "2. Агент"
if [[ ! -f "$APK" ]]; then
  warn "APK агента не собран — собираю"
  (cd "$ROOT/agent" && JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home}" ./gradlew assembleDebug -q)
fi
adb -d install -r "$APK" >/dev/null
ok "установлен $(adb -d shell dumpsys package $PKG | grep -m1 versionName | tr -d ' \r')"

adb -d shell pm grant $PKG android.permission.WRITE_SECURE_SETTINGS
adb -d shell appops set $PKG GET_USAGE_STATS allow
adb -d shell pm grant $PKG android.permission.DUMP   # заряд контроллеров (dumpsys OVRRemoteService)
ok "права: WRITE_SECURE_SETTINGS, статистика использования, DUMP"

# Accessibility: добавляем свой сервис к уже включённым, а не заменяем список
CURRENT="$(adb -d shell settings get secure enabled_accessibility_services | tr -d '\r')"
if [[ "$CURRENT" == "null" || -z "$CURRENT" ]]; then
  NEW="$A11Y"
elif [[ ":$CURRENT:" == *":$A11Y:"* ]]; then
  NEW="$CURRENT"
else
  NEW="$CURRENT:$A11Y"
fi
adb -d shell settings put secure enabled_accessibility_services "$NEW"
adb -d shell settings put secure accessibility_enabled 1
ok "Accessibility-сервис агента включён"

# Без этого Android забудет ключ ADB через 7 дней без подключений
adb -d shell settings put global adb_allowed_connection_time 0
ok "таймер ключа ADB отключён"

# --- 3. регистрация на сервере -------------------------------------------------
say "3. Регистрация на сервере"
ANDROID_ID="$(adb -d shell am broadcast -n $PKG/.ProvisionReceiver -a $PKG.PROVISION_PING 2>/dev/null | grep -o 'android_id=[0-9a-f]*' | cut -d= -f2 || true)"
BODY="$(python3 -c 'import json,sys; print(json.dumps({"label": sys.argv[1], "serial": sys.argv[2], "androidId": sys.argv[3] or None}))' "$LABEL" "$SERIAL" "$ANDROID_ID")"
RESP="$(curl -sf -X POST "$SERVER/api/headsets" -H "Authorization: Bearer $HM_ADMIN_TOKEN" \
  -H 'Content-Type: application/json' -d "$BODY")" || die "сервер отклонил регистрацию (неверный HM_ADMIN_TOKEN?)"
HEADSET_ID="$(echo "$RESP" | json '["headsetId"]')"
TOKEN="$(echo "$RESP" | json '["token"]')"
[[ "$(echo "$RESP" | json '["created"]')" == "True" ]] && ok "новый шлем «$LABEL»" || ok "шлем уже был, запись сохранена, токен обновлён"

OUT="$(adb -d shell am broadcast -n $PKG/.ProvisionReceiver -a $PKG.PROVISION \
  --es server_url "$SERVER" --es headset_id "$HEADSET_ID" --es token "$TOKEN")"
unset TOKEN RESP
[[ "$OUT" == *'data="ok'* ]] || die "агент не принял настройки: $OUT"
ok "агент получил адрес сервера и токен"

# --- 4. ключ ADB (вариант C) ---------------------------------------------------
if [[ $WITH_KEY -eq 1 ]]; then
  say "4. Ключ ADB для «сильных» команд"
  TMP="$(mktemp -d)"
  chmod 700 "$TMP"
  restore_adb() {
    # вернуть обычный adb-сервер с ключом этого компьютера и стереть временный ключ
    adb kill-server >/dev/null 2>&1 || true
    adb start-server >/dev/null 2>&1 || true
    rm -rf "$TMP"
  }
  trap restore_adb EXIT

  # adb ищет ключ в $HOME/.android — подменяем HOME, чтобы шлему предъявлялся ТОЛЬКО новый ключ
  mkdir -p "$TMP/.android"
  adb keygen "$TMP/.android/adbkey" >/dev/null 2>&1
  PUB_PREFIX="$(cut -c1-40 "$TMP/.android/adbkey.pub")"
  FP="$(awk '{print $1}' "$TMP/.android/adbkey.pub" | base64 -d | md5 | sed 's/../&:/g; s/:$//' | tr a-f A-F)"

  adb kill-server >/dev/null 2>&1 || true
  HOME="$TMP" ANDROID_USER_HOME="$TMP/.android" adb start-server >/dev/null 2>&1
  printf '\n   \033[1mНаденьте шлем.\033[0m В окне «Allow USB debugging?» (отпечаток …%s)\n' "${FP: -11}"
  printf '   поставьте галочку \033[1m«Always allow from this computer»\033[0m и нажмите Allow.\n   Жду до 2 минут…\n'
  for _ in $(seq 1 60); do
    [[ "$(HOME="$TMP" ANDROID_USER_HOME="$TMP/.android" adb -d get-state 2>/dev/null)" == "device" ]] && break
    sleep 2
  done
  [[ "$(HOME="$TMP" ANDROID_USER_HOME="$TMP/.android" adb -d get-state 2>/dev/null)" == "device" ]] \
    || die "ключ не разрешён в шлеме за 2 минуты — запустите скрипт ещё раз"

  # Без галочки ключ доверяется только до отключения кабеля и беспроводная отладка его не примет
  sleep 1
  LINE="$(adb -d logcat -d 2>/dev/null | grep 'AdbDebuggingManager' | grep 'Logging key' | grep -F "$PUB_PREFIX" | tail -1 || true)"
  if [[ "$LINE" != *"alwaysAllow = true"* ]]; then
    die "в шлеме не поставлена галочка «Always allow from this computer». Запустите скрипт ещё раз и поставьте её"
  fi
  ok "ключ разрешён навсегда (alwaysAllow = true)"

  # Сертификат как у самого adb: самоподписанный CA с этим ключом
  cat > "$TMP/cert.cnf" <<'EOF'
[req]
distinguished_name = dn
x509_extensions = v3
prompt = no
[dn]
C = US
O = Android
CN = Adb
[v3]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign,digitalSignature
subjectKeyIdentifier = hash
EOF
  openssl req -new -x509 -key "$TMP/.android/adbkey" -config "$TMP/cert.cnf" -days 3650 -set_serial 1 \
    -sha256 -outform DER -out "$TMP/cert.der" 2>/dev/null
  openssl pkcs8 -topk8 -nocrypt -in "$TMP/.android/adbkey" -outform DER -out "$TMP/key.der"

  OUT="$(HOME="$TMP" ANDROID_USER_HOME="$TMP/.android" adb -d shell am broadcast -n $PKG/.ProvisionReceiver \
    -a $PKG.PROVISION_KEY --es key_b64 "$(base64 -i "$TMP/key.der" | tr -d '\n')" \
    --es cert_b64 "$(base64 -i "$TMP/cert.der" | tr -d '\n')")"
  [[ "$OUT" == *'data="ok'* ]] || die "агент не принял ключ: ${OUT//key_b64*/…}"
  ok "ключ передан агенту ($(echo "$OUT" | grep -o 'fingerprint=[0-9a-f]*'))"

  restore_adb
  trap - EXIT
  ok "временный ключ стёрт с компьютера"
else
  say "4. Ключ ADB пропущен (--no-key): «закрыть игру» и «перезагрузка» будут недоступны"
fi

# --- 5. итог -------------------------------------------------------------------
say "5. Шлем на сервере"
for _ in $(seq 1 15); do
  H="$(curl -sf -H "Authorization: Bearer $HM_ADMIN_TOKEN" "$SERVER/api/headsets" | python3 -c "import json,sys; h=[x for x in json.load(sys.stdin) if x['id']=='$HEADSET_ID']; print(json.dumps(h[0]) if h else '')")"
  [[ -n "$H" && "$(echo "$H" | json '["online"]')" == "True" ]] && break
  sleep 2
done
if [[ -n "$H" && "$(echo "$H" | json '["online"]')" == "True" ]]; then
  ok "«$LABEL» онлайн, батарея $(echo "$H" | json '["battery"]')%, ADB: $(echo "$H" | json '["adb"]')"
  if [[ "$(echo "$H" | json '["adb"]')" == "waiting_confirmation" ]]; then
    warn "наденьте шлем и нажмите «Always allow on this network» — это нужно после каждого включения шлема"
  fi
else
  warn "шлем пока не появился онлайн — проверьте журнал агента: adb shell run-as $PKG cat files/agent.log"
fi
printf '\nГотово. Дашборд: %s\n' "$SERVER"
