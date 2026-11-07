package com.arena.agent

import android.app.Application
import android.content.Context

class AgentApp : Application() {
    override fun onCreate() {
        super.onCreate()
        AgentLog.init(this)
    }
}

/** Что агент получает при настройке (provision.sh): куда подключаться и как представляться. */
class AgentConfig(context: Context) {
    private val prefs = context.getSharedPreferences("config", Context.MODE_PRIVATE)

    val serverUrl: String? get() = prefs.getString(KEY_SERVER, null)
    val headsetId: String? get() = prefs.getString(KEY_ID, null)
    val token: String? get() = prefs.getString(KEY_TOKEN, null)

    val isProvisioned: Boolean get() = serverUrl != null && headsetId != null && token != null

    fun save(serverUrl: String, headsetId: String, token: String) {
        prefs.edit()
            .putString(KEY_SERVER, serverUrl)
            .putString(KEY_ID, headsetId)
            .putString(KEY_TOKEN, token)
            .apply()
    }

    private companion object {
        const val KEY_SERVER = "server_url"
        const val KEY_ID = "headset_id"
        const val KEY_TOKEN = "token"
    }
}
