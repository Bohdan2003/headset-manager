package com.arena.agent

import android.content.Context
import android.content.pm.PackageManager
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Заряд контроллеров. Quest отдаёт его только в `dumpsys OVRRemoteService` (строки «Paired device»):
 *   Paired device: …, Type:  Right, … Battery:  40%, … ExternalStatus: CONNECTED_ACTIVE, …
 * Нужно право DUMP. Пробуем сначала сами (если DUMP выдан через pm grant), иначе через локальный ADB.
 */
object Controllers {
    private val LINE = Regex("""Type:\s*(Left|Right),.*?Battery:\s*(\d+)%.*?ExternalStatus:\s*(\w+)""")

    /** Последнее прочитанное; null — прочитать не удалось ни разу. */
    @Volatile
    var last: JSONArray? = null
        private set

    @Volatile
    private var loggedSource: String? = null

    /** Вызывать не из главного потока: dumpsys и ADB занимают до пары секунд. */
    fun refresh(context: Context, adb: AdbManager) {
        val (source, dump) = readDirect(context)?.let { "direct" to it }
            ?: adb.takeIf { it.status == "ready" }?.shell("dumpsys OVRRemoteService")?.let { "adb" to it }
            ?: return
        val parsed = parse(dump)
        if (parsed.length() == 0) return // служба ответила, но без контроллеров (формат сменился?)
        last = parsed
        if (loggedSource != source) {
            AgentLog.i("controllers via $source: $parsed")
            loggedSource = source
        }
    }

    fun parse(dump: String): JSONArray {
        val bySide = linkedMapOf<String, JSONObject>()
        for (m in LINE.findAll(dump)) {
            val (type, battery, status) = m.destructured
            val side = type.lowercase()
            if (side in bySide) continue // первая строка на сторону — актуальная пара
            bySide[side] = JSONObject()
                .put("side", side)
                .put("battery", battery.toInt())
                .put("connected", status.startsWith("CONNECTED"))
        }
        return JSONArray(bySide.values)
    }

    /** dumpsys из процесса агента — работает, только если агенту выдано право DUMP. */
    private fun readDirect(context: Context): String? {
        if (context.checkSelfPermission("android.permission.DUMP") != PackageManager.PERMISSION_GRANTED) return null
        return try {
            val p = ProcessBuilder("dumpsys", "OVRRemoteService").redirectErrorStream(true).start()
            val out = p.inputStream.bufferedReader().readText()
            if (!p.waitFor(5, TimeUnit.SECONDS)) p.destroy()
            out.takeIf { "Paired device" in it }
        } catch (e: Exception) {
            if (loggedSource != "direct-failed") {
                AgentLog.i("controllers: direct dumpsys failed: ${e.message}")
                loggedSource = "direct-failed"
            }
            null
        }
    }
}
