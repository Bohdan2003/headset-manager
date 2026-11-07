package com.arena.agent

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.SystemClock
import android.provider.Settings
import java.net.ConnectException
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import javax.net.ssl.SSLException

/**
 * Поднимает локальный ADB (вариант C): включает беспроводную отладку, ждёт, пока оператор
 * нажмёт «Allow» в шлеме, находит порт и проверяет вход в adbd ключом агента.
 * Статус уходит на сервер в heartbeat (поле adb).
 *
 * Сами «сильные» команды (закрыть игру, перезагрузка) — в следующем срезе: они будут
 * подключаться к adbd по требованию через [connect].
 */
class AdbManager(private val context: Context, private val onStatus: (String) -> Unit) {

    @Volatile
    var status: String = "connecting"
        private set

    private val executor = Executors.newSingleThreadExecutor { Thread(it, "adb") }
    private val running = AtomicBoolean(false)

    /** Запустить проверку (при старте агента и каждый раз, когда появляется сеть). */
    fun refresh() {
        if (!running.compareAndSet(false, true)) return
        executor.execute {
            try {
                runChain()
            } catch (e: Exception) {
                AgentLog.e("adb: chain failed", e)
                set("error")
            } finally {
                running.set(false)
            }
        }
    }

    /**
     * Снова показать в шлеме окно «Allow wireless debugging»: оно появляется при включении
     * настройки, поэтому выключаем и включаем. Если доступ уже есть, не трогаем: это его сбросит.
     * Вызывать не из главного потока.
     */
    fun requestAccess() {
        if (status == "ready") return
        Settings.Global.putInt(context.contentResolver, ADB_WIFI, 0)
        Thread.sleep(1_000)
        Settings.Global.putInt(context.contentResolver, ADB_WIFI, 1)
        AgentLog.i("adb: access requested again")
        refresh()
    }

    /** Сеть пропала: Android выключает беспроводную отладку, прежний «ready» больше не верен. */
    fun networkLost() = set("no_wifi")

    @Volatile
    private var lastPort: Int? = null

    /**
     * Выполнить shell-команду через локальный ADB (для «сильных» команд).
     * Сначала пробует последний рабочий порт, потом ищет через mDNS.
     * null — войти в adbd не удалось. Вызывать не из главного потока.
     */
    fun shell(command: String, readTimeoutMs: Int? = null): String? {
        val key = AdbKey.load(context) ?: return null
        fun runOn(port: Int): String? = try {
            LocalAdb(key).use { adb ->
                adb.connect("127.0.0.1", port)
                lastPort = port
                adb.shell(command, readTimeoutMs)
            }
        } catch (_: ConnectException) {
            null // порт сменился (старая запись mDNS)
        } catch (e: Exception) {
            AgentLog.e("adb: shell on port $port failed", e)
            null
        }

        // mDNS занимает ~2 с, поэтому к нему обращаемся, только если старый порт не отвечает
        val known = lastPort
        known?.let { port -> runOn(port)?.let { return it } }
        for (port in MdnsFinder.findPorts(context, 10_000)) {
            if (port != known) runOn(port)?.let { return it }
        }
        AgentLog.i("adb: no working port for shell")
        refresh() // статус «ready» устарел — пусть цепочка проверит заново
        return null
    }

    private fun runChain() {
        val key = AdbKey.load(context)
        if (key == null) {
            set("key_missing")
            return
        }
        if (!wifiConnected()) {
            set("no_wifi") // NetworkCallback в AgentService вызовет refresh(), когда сеть появится
            return
        }

        // Повторяем, пока не войдём: если вход не удался из-за выключенной отладки
        // (окно «Allow» ещё не подтверждено), возвращаемся к ожиданию.
        while (true) {
            if (!wifiConnected()) {
                set("no_wifi")
                return
            }
            if (!waitForAdbWifi()) return

            // 2. Найти порт и войти в adbd. Порт мог только что смениться — несколько попыток.
            set("connecting")
            for (attempt in 1..5) {
                for (port in MdnsFinder.findPorts(context, 15_000)) {
                    try {
                        LocalAdb(key).use { adb ->
                            adb.connect("127.0.0.1", port)
                            val id = adb.shell("id")
                            if ("uid=2000" in id) {
                                AgentLog.i("adb: ready on port $port")
                                lastPort = port
                                set("ready")
                                return
                            }
                            AgentLog.e("adb: unexpected id output: $id")
                        }
                    } catch (_: ConnectException) {
                        AgentLog.i("adb: port $port refused")
                    } catch (e: SSLException) {
                        // adbd не доверяет нашему ключу: шлем его забыл — нужна настройка кабелем
                        AgentLog.e("adb: key rejected on port $port", e)
                        set("key_rejected")
                        return
                    }
                }
                AgentLog.i("adb: no working port (attempt $attempt)")
                if (!adbWifiEnabled()) break // отладку снова выключили — незачем перебирать порты
                Thread.sleep(2_000)
            }
            if (adbWifiEnabled()) break
            AgentLog.i("adb: wireless debugging is off again, back to waiting")
        }
        set("error")
    }

    /**
     * Включить беспроводную отладку и дождаться «Allow» от оператора.
     * false — ждать дальше нельзя (нет Wi-Fi или нет права).
     */
    private fun waitForAdbWifi(): Boolean {
        if (adbWifiEnabled()) return true
        if (!writeAdbWifi()) return false
        // Сразу после записи система ещё показывает 1 и только потом сбрасывает в 0,
        // пока окно не подтверждено. Без паузы мы бы решили, что отладка уже включена.
        Thread.sleep(2_000)
        var writtenAt = SystemClock.elapsedRealtime()
        while (!adbWifiEnabled()) {
            set("waiting_confirmation")
            if (!wifiConnected()) {
                set("no_wifi")
                return false
            }
            // Если окно закрыли кнопкой Cancel, оно само не появится — через 5 мин попросим снова
            if (SystemClock.elapsedRealtime() - writtenAt > REASK_MS) {
                if (!writeAdbWifi()) return false
                writtenAt = SystemClock.elapsedRealtime()
            }
            Thread.sleep(2_000)
        }
        return true
    }

    private fun adbWifiEnabled() = Settings.Global.getInt(context.contentResolver, ADB_WIFI, 0) == 1

    private fun writeAdbWifi(): Boolean = try {
        Settings.Global.putInt(context.contentResolver, ADB_WIFI, 1)
        AgentLog.i("adb: adb_wifi_enabled=1 written, waiting for «Allow» in the headset")
        true
    } catch (e: SecurityException) {
        AgentLog.e("adb: no WRITE_SECURE_SETTINGS — re-provision needed", e)
        set("error")
        false
    }

    private fun wifiConnected(): Boolean {
        val cm = context.getSystemService(ConnectivityManager::class.java)
        val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
        return caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
    }

    private fun set(value: String) {
        if (value == status) return
        AgentLog.i("adb: $status -> $value")
        status = value
        onStatus(value)
    }

    private companion object {
        const val ADB_WIFI = "adb_wifi_enabled"
        const val REASK_MS = 5 * 60_000L
    }
}
