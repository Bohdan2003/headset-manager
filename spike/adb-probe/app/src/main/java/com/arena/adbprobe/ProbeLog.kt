package com.arena.adbprobe

import android.content.Context
import android.util.Log
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Пишет и в logcat (тег AdbProbe), и в files/probe.log — чтобы журнал пережил перезагрузку. */
object ProbeLog {
    private const val TAG = "AdbProbe"
    private val fmt = SimpleDateFormat("MM-dd HH:mm:ss.SSS", Locale.US)

    @Volatile
    private var file: File? = null

    fun init(context: Context) {
        if (file == null) file = File(context.filesDir, "probe.log")
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
        try {
            file?.appendText("${fmt.format(Date())} $level $msg\n")
        } catch (_: Exception) {
        }
    }
}
