package com.arena.adbprobe

import android.annotation.SuppressLint
import android.app.ActivityManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Settings

/**
 * Команды с компьютера через `adb shell am broadcast`:
 *  - PROVISION: принять ключ (key_b64 = PKCS#8 DER, cert_b64 = X.509 DER), вернуть android_id агента;
 *  - RUN: запустить проверку вручную;
 *  - KILL_BG: закрыть приложение pkg, ушедшее в фон, обычным правом (без shell);
 *  - SLEEP: mode=off|on — отправить broadcast vrpowermanager обычным приложением (без shell);
 *  - LAUNCH: запустить игру pkg обычным приложением (без shell);
 *  - GUARD: pkg — возвращать игрока в эту игру; без pkg — выключить.
 */
class ControlReceiver : BroadcastReceiver() {
    @SuppressLint("HardwareIds")
    override fun onReceive(context: Context, intent: Intent) {
        ProbeLog.init(context)
        when (intent.action) {
            ACTION_PROVISION -> {
                val key = intent.getStringExtra("key_b64")
                val cert = intent.getStringExtra("cert_b64")
                if (key.isNullOrEmpty() || cert.isNullOrEmpty()) {
                    ProbeLog.e("PROVISION: key_b64/cert_b64 missing")
                    resultCode = 1
                    resultData = "error: key_b64/cert_b64 missing"
                    return
                }
                try {
                    val fp = AdbKey.save(context, key, cert)
                    val androidId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
                    ProbeLog.i("PROVISION: key saved, fingerprint=$fp, android_id=$androidId")
                    resultCode = 0
                    resultData = "ok android_id=$androidId fingerprint=$fp"
                } catch (e: Exception) {
                    ProbeLog.e("PROVISION: failed", e)
                    resultCode = 1
                    resultData = "error: ${e.message}"
                }
            }
            ACTION_RUN -> {
                ProbeLog.i("RUN received")
                ProbeService.start(context, "manual")
                resultData = "started"
            }
            ACTION_KILL_BG -> {
                val pkg = intent.getStringExtra("pkg")
                if (pkg == null || !PACKAGE_RE.matches(pkg)) {
                    resultCode = 1
                    resultData = "error: bad pkg"
                    return
                }
                context.getSystemService(ActivityManager::class.java).killBackgroundProcesses(pkg)
                ProbeLog.i("KILL_BG: killBackgroundProcesses($pkg) called")
                resultData = "called"
            }
            ACTION_SLEEP -> {
                // off = не засыпать при снятии (prox_close), on = обычное поведение (automation_disable)
                val action = when (intent.getStringExtra("mode")) {
                    "off" -> "com.oculus.vrpowermanager.prox_close"
                    "on" -> "com.oculus.vrpowermanager.automation_disable"
                    else -> null
                }
                if (action == null) {
                    resultCode = 1
                    resultData = "error: mode must be off|on"
                    return
                }
                context.sendBroadcast(Intent(action))
                ProbeLog.i("SLEEP: sent $action as uid ${android.os.Process.myUid()}")
                resultData = "sent $action"
            }
            ACTION_LAUNCH -> {
                val pkg = intent.getStringExtra("pkg")
                if (pkg == null || !PACKAGE_RE.matches(pkg)) {
                    resultCode = 1
                    resultData = "error: bad pkg"
                    return
                }
                resultData = if (Launcher.launch(context, pkg, "receiver")) "ok" else "failed"
            }
            ACTION_GUARD -> {
                val pkg = intent.getStringExtra("pkg")
                if (pkg != null && !PACKAGE_RE.matches(pkg)) {
                    resultCode = 1
                    resultData = "error: bad pkg"
                    return
                }
                Guard.set(context, pkg)
                ProbeLog.i("GUARD: ${pkg ?: "off"}")
                resultData = "guard=${pkg ?: "off"}"
            }
        }
    }

    companion object {
        const val ACTION_PROVISION = "com.arena.adbprobe.PROVISION"
        const val ACTION_RUN = "com.arena.adbprobe.RUN"
        const val ACTION_KILL_BG = "com.arena.adbprobe.KILL_BG"
        const val ACTION_SLEEP = "com.arena.adbprobe.SLEEP"
        const val ACTION_LAUNCH = "com.arena.adbprobe.LAUNCH"
        const val ACTION_GUARD = "com.arena.adbprobe.GUARD"
        private val PACKAGE_RE = Regex("^[a-zA-Z0-9_.]+$")
    }
}
