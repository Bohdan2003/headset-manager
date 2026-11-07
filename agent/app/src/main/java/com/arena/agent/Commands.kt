package com.arena.agent

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.view.Gravity
import android.widget.TextView
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.Executors

private val PACKAGE_RE = Regex("^[a-zA-Z0-9_.]+$")

private const val UPDATE_APK = "/data/local/tmp/arena-agent.apk"
private const val INSTALL_TIMEOUT_MS = 180_000

/** Сколько защита не вмешивается, пока оператор закрывает или перезапускает игру. */
private const val HOLD_MS = 15_000L

/**
 * Выполнение команд сервера. Агент делает только то, что есть в этом списке;
 * имя пакета проверяется ещё раз, даже если сервер его уже проверил.
 *
 * Команды обычными правами (B) отвечают сразу. Команды через локальный ADB (C) —
 * в отдельном потоке: поиск порта и вход в adbd занимают секунды.
 */
class CommandExecutor(private val context: Context, private val adb: AdbManager) {

    private val adbThread = Executors.newSingleThreadExecutor { Thread(it, "adb-cmd") }

    fun execute(cmd: JSONObject, reply: (JSONObject) -> Unit) {
        val id = cmd.optString("id")
        val name = cmd.optString("cmd")
        val p = cmd.optJSONObject("params") ?: JSONObject()
        AgentLog.i("command $name $p")
        when (name) {
            "close_game", "restart_game", "reboot", "sleep", "power_off", "update_agent" -> adbThread.execute { reply(guarded(id, name) { viaAdb(id, name, p) }) }
            // ADB ещё нет, но запись настройки с паузой не должна задерживать heartbeat
            "request_access" -> adbThread.execute {
                reply(guarded(id, name) {
                    adb.requestAccess()
                    ok(id)
                })
            }
            else -> reply(guarded(id, name) { direct(id, name, p) })
        }
    }

    /** Шлем усыпили кнопкой питания: разбудить и запустить игру заново. */
    fun restartAfterPowerPress(target: String) = adbThread.execute {
        Guard.hold(HOLD_MS)
        val out = adb.shell("input keyevent KEYCODE_WAKEUP; am force-stop $target; pidof $target || echo closed")
        when {
            out == null -> AgentLog.e("power restart: no adb, cannot wake the headset")
            "closed" !in out -> AgentLog.e("power restart: $target still running: $out")
            Launcher.launch(context, target) -> {
                AgentLog.i("power restart: $target restarted")
                AgentEvents.emit("power_restart", JSONObject().put("pkg", target))
                return@execute
            }
            else -> AgentLog.e("power restart: closed but cannot launch $target")
        }
        Guard.hold(0) // не вышло — пусть защита вернёт игру обычным способом
    }

    private fun direct(id: String, name: String, p: JSONObject): JSONObject = when (name) {
        "launch" -> {
            val pkg = pkg(p.getString("pkg"))
            if (Launcher.launch(context, pkg)) {
                Guard.set(context, if (p.optBoolean("guard")) pkg else null)
                ok(id)
            } else {
                fail(id, "failed", "not installed or no launch activity: $pkg")
            }
        }
        "show_menu" -> {
            Guard.set(context, null) // иначе защита сразу вернёт игрока в игру
            MenuActivity.show(context)
            ok(id)
        }
        "set_sleep" -> {
            if (p.getBoolean("disabled")) Sleep.disable(context) else Sleep.enable(context)
            ok(id)
        }
        "guard" -> {
            val target = when {
                p.optBoolean("current") -> CurrentApp.pkg?.takeIf { it != context.packageName && !isSystemPackage(it) }
                    ?: return fail(id, "failed", "no game running (current: ${CurrentApp.pkg})")
                p.isNull("pkg") -> null
                else -> pkg(p.getString("pkg"))
            }
            Guard.set(context, target)
            ok(id)
        }
        else -> fail(id, "not_allowed", "unknown command: $name")
    }

    private fun viaAdb(id: String, name: String, p: JSONObject): JSONObject {
        if (adb.status != "ready") return fail(id, "no_adb", "adb status: ${adb.status}")
        return when (name) {
            "close_game" -> closeGame(id, p)
            "restart_game" -> restartGame(id, p)
            "update_agent" -> updateAgent(id, p)
            "reboot" -> powerAction(id, "reboot")
            "power_off" -> powerAction(id, "reboot -p")
            "sleep" -> {
                Guard.expectSleep() // это оператор, а не игрок нажал кнопку: игру не перезапускать
                adb.shell("input keyevent KEYCODE_SLEEP")?.let { ok(id) }
                    ?: fail(id, "no_adb", "cannot connect to adbd")
            }
            else -> fail(id, "not_allowed", "unknown command: $name")
        }
    }

    private fun closeGame(id: String, p: JSONObject): JSONObject {
        val target = if (p.isNull("pkg")) CurrentApp.pkg else pkg(p.getString("pkg"))
        if (target == null || target == context.packageName || isSystemPackage(target)) {
            return fail(id, "failed", "nothing to close (current: ${CurrentApp.pkg})")
        }
        forceStop(id, target)?.let { return it }
        Guard.set(context, null) // только после закрытия: если не вышло, защита остаётся
        MenuActivity.show(context) // игрок видит наш экран ожидания, а не домашнее окружение Meta
        return ok(id)
    }

    /** Закрыть игру и запустить заново. Защита остаётся включённой. */
    private fun restartGame(id: String, p: JSONObject): JSONObject {
        val current = CurrentApp.pkg?.takeIf { it != context.packageName && !isSystemPackage(it) }
        val target = (if (p.isNull("pkg")) current ?: Guard.get(context) else pkg(p.getString("pkg")))
            ?: return fail(id, "failed", "nothing to restart (current: ${CurrentApp.pkg})")
        forceStop(id, target)?.let { return it }
        if (!Launcher.launch(context, target)) return fail(id, "failed", "closed but cannot launch: $target")
        return ok(id)
    }

    /** Закрыть игру через ADB. null — закрыта; иначе ack с ошибкой. */
    private fun forceStop(id: String, target: String): JSONObject? {
        Guard.hold(HOLD_MS) // иначе защита успеет вернуть игру, пока мы её закрываем
        val out = adb.shell("am force-stop $target; pidof $target || echo closed")
        val result = when {
            out == null -> fail(id, "no_adb", "cannot connect to adbd")
            "closed" !in out -> fail(id, "failed", "still running: $out")
            else -> null
        }
        if (result != null) Guard.hold(0)
        else AgentLog.i("closed $target")
        return result
    }

    /**
     * Обновление по Wi-Fi: скачать новую версию с сервера и поставить её через локальный ADB.
     * Соединение с adbd держим открытым до конца: команда в фоне (nohup) не запускалась, её
     * завершал adbd вместе с соединением. Android сам завершит наш процесс, когда новая версия
     * будет установлена, поэтому ack уходит заранее. Новый агент поднимается сам.
     */
    private fun updateAgent(id: String, p: JSONObject): JSONObject {
        val target = p.getLong("versionCode")
        val own = context.packageManager.getPackageInfo(context.packageName, 0).longVersionCode
        if (own >= target) return ok(id)

        val base = AgentConfig(context).serverUrl ?: return updateFailed(id, "failed", "no server url")
        val path = p.getString("path")
        require(path.startsWith("/")) { "bad path" }
        val dir = context.getExternalFilesDir(null) ?: return updateFailed(id, "failed", "no external storage")
        val apk = File(dir, "agent-update.apk")

        val digest = MessageDigest.getInstance("SHA-256")
        val request = Request.Builder().url(base.trimEnd('/') + path).build()
        OkHttpClient().newCall(request).execute().use { r ->
            if (!r.isSuccessful) return updateFailed(id, "failed", "download: HTTP ${r.code}")
            val body = r.body ?: return updateFailed(id, "failed", "download: empty body")
            val total = body.contentLength()
            var done = 0L
            var shown = -1
            apk.outputStream().use { out ->
                body.byteStream().use { input ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        val n = input.read(buffer)
                        if (n < 0) break
                        out.write(buffer, 0, n)
                        digest.update(buffer, 0, n)
                        done += n
                        val percent = if (total > 0) (done * 100 / total).toInt() else 0
                        if (percent >= shown + 5) {
                            shown = percent
                            progress("downloading", percent)
                        }
                    }
                }
            }
        }
        val sha = digest.digest().joinToString("") { "%02x".format(it) }
        if (sha != p.getString("sha256")) {
            apk.delete()
            return updateFailed(id, "failed", "checksum mismatch")
        }

        // Файл агента читает shell, а устанавливать лучше из его папки: так установка не зависит от агента
        val copy = adb.shell("cp ${apk.absolutePath} $UPDATE_APK && echo copied")
            ?: return updateFailed(id, "no_adb", "cannot connect to adbd")
        if ("copied" !in copy) return updateFailed(id, "failed", "copy: $copy")
        apk.delete()

        adbThread.execute {
            Thread.sleep(1000) // ack успевает уйти на сервер
            progress("installing", 100)
            AgentLog.i("updating agent to version code $target")
            val out = adb.shell("pm install -r $UPDATE_APK; rm -f $UPDATE_APK", INSTALL_TIMEOUT_MS)
            // Дошли сюда — значит, процесс не завершён. При успехе это ненадолго
            if (out == null || "Success" !in out) {
                val reason = out?.trim()?.take(300) ?: "connection to adbd lost"
                AgentLog.e("agent update failed: $reason")
                AgentEvents.emit("update_failed", JSONObject().put("reason", reason))
            }
        }
        return ok(id)
    }

    private fun progress(stage: String, percent: Int) {
        AgentEvents.emit("update_progress", JSONObject().put("stage", stage).put("percent", percent))
    }

    private fun updateFailed(id: String, reason: String, detail: String): JSONObject {
        AgentEvents.emit("update_failed", JSONObject().put("reason", detail))
        return fail(id, reason, detail)
    }

    /** Перезагрузка или выключение: после них связь оборвётся, поэтому ack уходит заранее. */
    private fun powerAction(id: String, command: String): JSONObject {
        // Сначала убеждаемся, что команда точно выполнится, потом подтверждаем, потом выполняем
        val check = adb.shell("id") ?: return fail(id, "no_adb", "cannot connect to adbd")
        if ("uid=2000" !in check) return fail(id, "failed", "unexpected id: $check")
        adbThread.execute {
            Thread.sleep(1000) // ack успевает уйти на сервер
            RebootHook.beforeReboot?.invoke()
            Thread.sleep(500)
            AgentLog.i("power action: $command")
            adb.shell(command)
            // Если мы всё ещё живы через 10 с — команда не сработала, возвращаемся на связь
            Thread.sleep(10_000)
            AgentLog.e("$command did not happen, reconnecting")
            RebootHook.rebootFailed?.invoke()
        }
        return ok(id)
    }

    private inline fun guarded(id: String, name: String, block: () -> JSONObject): JSONObject = try {
        block()
    } catch (e: JSONException) {
        fail(id, "bad_params", e.message)
    } catch (e: IllegalArgumentException) {
        fail(id, "bad_params", e.message)
    } catch (e: Exception) {
        AgentLog.e("command $name failed", e)
        fail(id, "failed", "${e.javaClass.simpleName}: ${e.message}")
    }

    private fun pkg(value: String): String {
        require(PACKAGE_RE.matches(value)) { "bad package name" }
        return value
    }

    private fun ok(id: String) = JSONObject().put("type", "ack").put("id", id).put("ok", true)

    private fun fail(id: String, reason: String, detail: String?): JSONObject {
        AgentLog.i("command $id failed: $reason $detail")
        return JSONObject().put("type", "ack").put("id", id).put("ok", false)
            .put("reason", reason).put("detail", detail?.take(500) ?: JSONObject.NULL)
    }
}

/** Что сделать перед перезагрузкой шлема (AgentService закрывает соединение с сервером). */
object RebootHook {
    @Volatile
    var beforeReboot: (() -> Unit)? = null

    @Volatile
    var rebootFailed: (() -> Unit)? = null
}

/** Запуск игры обычными правами приложения (без shell). */
object Launcher {
    fun launch(context: Context, pkg: String): Boolean {
        val intent = context.packageManager.getLaunchIntentForPackage(pkg) ?: return false
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            AgentLog.i("launched $pkg")
            true
        } catch (e: Exception) {
            AgentLog.e("launch $pkg failed", e)
            false
        }
    }
}

/**
 * Установленные приложения с иконкой в лаунчере — для выбора игры на дашборде.
 * vr=true — приложение объявляет категорию com.oculus.intent.category.VR (так делают все VR-игры).
 */
fun installedApps(context: Context): JSONArray {
    val pm = context.packageManager
    val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
    val vr = pm.queryIntentActivities(Intent(Intent.ACTION_MAIN).addCategory(VR_CATEGORY), 0)
        .map { it.activityInfo.packageName }
        .toSet()
    val apps = JSONArray()
    pm.queryIntentActivities(launcher, 0)
        .map { it.activityInfo.packageName to it.loadLabel(pm).toString() }
        .filter { (pkg, _) -> pkg != context.packageName }
        .distinctBy { (pkg, _) -> pkg }
        .sortedBy { (_, title) -> title.lowercase() }
        .forEach { (pkg, title) ->
            apps.put(JSONObject().put("package", pkg).put("title", title).put("vr", pkg in vr))
        }
    return apps
}

private const val VR_CATEGORY = "com.oculus.intent.category.VR"

/**
 * «Наше меню»: экран ожидания между играми. Пока без кнопок — игрой управляет оператор
 * с дашборда. На Quest показывается как плоская панель в домашнем окружении.
 */
class MenuActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(TextView(this).apply {
            text = "Arena\n\nYour game will start soon.\nPlease wait."
            textSize = 32f
            gravity = Gravity.CENTER
            setPadding(48, 48, 48, 48)
        })
    }

    companion object {
        fun show(context: Context) {
            context.startActivity(
                Intent(context, MenuActivity::class.java)
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            )
        }
    }
}
