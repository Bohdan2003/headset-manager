package com.arena.adbprobe

import android.content.Context
import android.content.Intent

/** Запуск игры обычными правами приложения (без shell). */
object Launcher {
    fun launch(context: Context, pkg: String, source: String): Boolean {
        val intent = context.packageManager.getLaunchIntentForPackage(pkg)
        if (intent == null) {
            ProbeLog.e("launch[$source]: no launch intent for $pkg")
            return false
        }
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            ProbeLog.i("launch[$source]: startActivity($pkg) ok")
            true
        } catch (e: Exception) {
            ProbeLog.e("launch[$source]: startActivity($pkg) failed", e)
            false
        }
    }
}

/** Какую игру охранять (возвращать в неё игрока). Хранится между перезапусками. */
object Guard {
    private const val PREFS = "guard"
    private const val KEY = "pkg"

    fun get(context: Context): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null)

    fun set(context: Context, pkg: String?) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY, pkg).apply()
    }
}
