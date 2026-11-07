package com.arena.agent

import android.annotation.SuppressLint
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Settings

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED && intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return
        AgentLog.i(intent.action!!.substringAfterLast('.'))
        AgentService.start(context)
    }
}

/**
 * Настройка из provision.sh через `adb shell am broadcast`:
 *  - PROVISION: server_url, headset_id, token — куда подключаться и как представляться;
 *  - PROVISION_KEY: key_b64 (PKCS#8 DER), cert_b64 (X.509 DER) — ключ ADB, которому доверяет шлем;
 *  - PROVISION_PING: ничего не меняет, только возвращает ANDROID_ID (нужен для регистрации на сервере).
 * В ответ возвращает ANDROID_ID агента (он свой у каждого приложения).
 */
class ProvisionReceiver : BroadcastReceiver() {
    @SuppressLint("HardwareIds")
    override fun onReceive(context: Context, intent: Intent) {
        val androidId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
        if (intent.action == ACTION_PING) {
            resultCode = 0
            resultData = "ok android_id=$androidId"
            return
        }
        try {
            when (intent.action) {
                ACTION_PROVISION -> {
                    val url = intent.getStringExtra("server_url")
                    val id = intent.getStringExtra("headset_id")
                    val token = intent.getStringExtra("token")
                    require(!url.isNullOrBlank() && !id.isNullOrBlank() && !token.isNullOrBlank()) {
                        "server_url, headset_id and token are required"
                    }
                    AgentConfig(context).save(url, id, token)
                    AgentLog.i("provisioned: server=$url headset=$id")
                    resultData = "ok android_id=$androidId"
                }
                ACTION_PROVISION_KEY -> {
                    val key = intent.getStringExtra("key_b64")
                    val cert = intent.getStringExtra("cert_b64")
                    require(!key.isNullOrBlank() && !cert.isNullOrBlank()) { "key_b64 and cert_b64 are required" }
                    val fp = AdbKey.save(context, key, cert)
                    AgentLog.i("adb key provisioned, fingerprint=$fp")
                    resultData = "ok android_id=$androidId fingerprint=$fp"
                }
                else -> return
            }
            resultCode = 0
            AgentService.start(context, restart = true)
        } catch (e: Exception) {
            AgentLog.e("provision failed", e)
            resultCode = 1
            resultData = "error: ${e.message}"
        }
    }

    companion object {
        const val ACTION_PROVISION = "com.arena.agent.PROVISION"
        const val ACTION_PROVISION_KEY = "com.arena.agent.PROVISION_KEY"
        const val ACTION_PING = "com.arena.agent.PROVISION_PING"
    }
}
