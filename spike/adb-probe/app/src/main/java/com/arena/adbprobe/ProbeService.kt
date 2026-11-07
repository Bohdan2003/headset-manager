package com.arena.adbprobe

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.IBinder
import android.os.SystemClock
import android.provider.Settings

/**
 * Проходит шаги, которые потом будет делать агент при каждой загрузке,
 * и пишет результат каждого шага в журнал (logcat -s AdbProbe).
 */
class ProbeService : Service() {

    @Volatile
    private var running = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        ProbeLog.init(this)
        startForeground(NOTIFICATION_ID, notification())
        if (!running) {
            running = true
            val reason = intent?.getStringExtra(EXTRA_REASON) ?: "?"
            Thread({
                try {
                    runProbe(reason)
                } catch (e: Exception) {
                    ProbeLog.e("probe: crashed", e)
                } finally {
                    running = false
                    stopSelf()
                }
            }, "probe").start()
        }
        return START_NOT_STICKY
    }

    private fun runProbe(reason: String) {
        val t0 = SystemClock.elapsedRealtime()
        fun step(name: String, msg: String) =
            ProbeLog.i("[$name] +${(SystemClock.elapsedRealtime() - t0) / 1000}s $msg")

        step("start", "reason=$reason uptime=${SystemClock.elapsedRealtime() / 1000}s")

        // 1. Права, выданные кабелем, на месте?
        val wss = checkSelfPermission(Manifest.permission.WRITE_SECURE_SETTINGS) == PackageManager.PERMISSION_GRANTED
        step("grant", "WRITE_SECURE_SETTINGS=$wss")
        val a11y = Settings.Secure.getString(contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES) ?: ""
        step("a11y", "enabled=${a11y.contains(packageName)} list=\"$a11y\"")
        step("timer", "adb_allowed_connection_time=${Settings.Global.getString(contentResolver, "adb_allowed_connection_time")}")

        // 2. Ждём Wi-Fi
        if (!waitFor(120_000) { isWifiConnected() }) {
            step("wifi", "FAIL: no Wi-Fi in 120s")
            return
        }
        step("wifi", "connected")

        // 3. Включаем беспроводную отладку
        val before = Settings.Global.getInt(contentResolver, ADB_WIFI, 0)
        step("adb_wifi", "before=$before")
        if (before != 1) {
            try {
                Settings.Global.putInt(contentResolver, ADB_WIFI, 1)
                step("adb_wifi", "putInt(1) ok")
            } catch (e: SecurityException) {
                step("adb_wifi", "FAIL: SecurityException ${e.message}")
                return
            }
        }
        // Значение станет 1, только когда кто-то (наш a11y-сервис) нажмёт Allow в окне
        if (!waitFor(60_000) { Settings.Global.getInt(contentResolver, ADB_WIFI, 0) == 1 }) {
            step("adb_wifi", "FAIL: still 0 after 60s (dialog not confirmed?)")
            return
        }
        step("adb_wifi", "enabled=1")

        // 4–6. Ищем порт через mDNS и входим в adbd через 127.0.0.1.
        // Порт мог только что смениться, поэтому перебираем все найденные и повторяем.
        val key = try {
            AdbKey.load(this)
        } catch (e: Exception) {
            ProbeLog.e("key: load failed", e)
            null
        }
        if (key == null) {
            step("key", "FAIL: no key (send PROVISION first)")
            return
        }
        step("key", "loaded fingerprint=${AdbKey.fingerprint(key)}")

        val end = SystemClock.elapsedRealtime() + 45_000
        var attempt = 0
        while (true) {
            attempt++
            val ports = MdnsFinder.findPorts(this, 15_000)
            step("mdns", "attempt=$attempt ports=$ports")
            for (port in ports) {
                try {
                    LocalAdb(key).use { adb ->
                        adb.connect("127.0.0.1", port)
                        step("adb", "connected to 127.0.0.1:$port")
                        for (cmd in PROBE_COMMANDS) {
                            val out = adb.shell(cmd).trim().replace("\n", " | ")
                            step("shell", "$ $cmd -> $out")
                        }
                    }
                    step("done", "OK")
                    return
                } catch (e: java.net.ConnectException) {
                    step("adb", "port $port refused (stale mDNS record?)")
                } catch (e: Exception) {
                    ProbeLog.e("[adb] FAIL on port $port", e)
                    return
                }
            }
            if (SystemClock.elapsedRealtime() > end) {
                step("adb", "FAIL: no working port in 45s")
                return
            }
            Thread.sleep(2_000)
        }
    }

    private fun isWifiConnected(): Boolean {
        val cm = getSystemService(ConnectivityManager::class.java)
        val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
        return caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
    }

    private fun waitFor(timeoutMs: Long, check: () -> Boolean): Boolean {
        val end = SystemClock.elapsedRealtime() + timeoutMs
        while (SystemClock.elapsedRealtime() < end) {
            if (check()) return true
            Thread.sleep(1000)
        }
        return check()
    }

    private fun notification(): Notification {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL, "ADB Probe", NotificationManager.IMPORTANCE_LOW))
        return Notification.Builder(this, CHANNEL)
            .setContentTitle("ADB Probe")
            .setContentText("Проверка локального ADB")
            .setSmallIcon(android.R.drawable.stat_sys_warning)
            .build()
    }

    companion object {
        private const val ADB_WIFI = "adb_wifi_enabled"
        private const val CHANNEL = "probe"
        private const val NOTIFICATION_ID = 1
        private const val EXTRA_REASON = "reason"

        /** Фиксированный список: проверка прав и отключение сна (оно слетает при каждой загрузке). */
        private val PROBE_COMMANDS = listOf(
            "id",
            "am broadcast -a com.oculus.vrpowermanager.prox_close",
            "dumpsys vrpowermanager | grep -i 'virtual proximity'",
        )

        fun start(context: Context, reason: String) {
            context.startForegroundService(
                Intent(context, ProbeService::class.java).putExtra(EXTRA_REASON, reason)
            )
        }
    }
}
