#!/usr/bin/env bash
# Проверка возможностей Meta Quest через ADB.
# Запуск: bash check_quest.sh <package_игры_для_теста>
# Пример: bash check_quest.sh com.beatgames.beatsaber
# Результат сохраняется в quest_report.txt

PKG="$1"
OUT="quest_report.txt"
: > "$OUT"

log()  { echo "$@" | tee -a "$OUT"; }
step() { log ""; log "=== $1 ==="; }
run()  { log "\$ adb $*"; adb "$@" 2>&1 | tee -a "$OUT"; log "[exit: ${PIPESTATUS[0]}]"; }

step "1. Устройство видно"
run devices -l

step "2. Модель и версия ОС"
run shell getprop ro.product.model
run shell getprop ro.build.version.release
run shell getprop ro.build.version.incremental

step "3. Установленные приложения (не системные)"
run shell pm list packages -3

step "4. Батарея"
run shell dumpsys battery

step "5. Текущее приложение на переднем плане"
run shell "dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'"

step "6. IP шлема в Wi-Fi"
run shell "ip -f inet addr show wlan0"

if [ -n "$PKG" ]; then
  step "7. Запуск игры $PKG"
  run shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1
  sleep 8
  run shell "dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'"

  step "8. Принудительное закрытие $PKG"
  run shell am force-stop "$PKG"
  sleep 3
  run shell "dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'"
else
  log ""
  log "Шаги 7-8 пропущены: не указан package игры."
fi

step "9. Отключение датчика приближения (сон при снятии шлема)"
run shell am broadcast -a com.oculus.vrpowermanager.automation_disable

step "10. Включение ADB по Wi-Fi"
run tcpip 5555

log ""
log "Готово. Отчёт: $OUT"
log "Дальше вручную: тест перезагрузки (см. инструкцию в чате)."
