package com.arena.agent

import android.content.Context
import android.util.Log
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Журнал агента: logcat (тег Agent) + files/agent.log, чтобы он пережил перезагрузку. */
object AgentLog {
    private const val TAG = "Agent"
    private const val MAX_BYTES = 1_000_000L
    private val fmt = SimpleDateFormat("MM-dd HH:mm:ss.SSS", Locale.US)

    @Volatile
    private var file: File? = null

    fun init(context: Context) {
        if (file == null) file = File(context.filesDir, "agent.log")
    }

    fun i(msg: String) {
        Log.i(TAG, msg)
        append("I", msg)
    }

    fun e(msg: String, t: Throwable? = null) {
        Log.e(TAG, msg, t)
        append("E", if (t == null) msg else "$msg: ${t.javaClass.simpleName}: ${t.message}")
    }

    @Synchronized
    private fun append(level: String, msg: String) {
        val f = file ?: return
        try {
            if (f.length() > MAX_BYTES) f.renameTo(File(f.parentFile, "agent.log.1"))
            f.appendText("${fmt.format(Date())} $level $msg\n")
        } catch (_: Exception) {
        }
    }
}
