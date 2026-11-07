package com.arena.agent

import android.accessibilityservice.AccessibilityService
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.view.accessibility.AccessibilityEvent

/** Батарея из системного «липкого» broadcast — для этого не нужны никакие права. */
data class Battery(val level: Int, val charging: Boolean, val tempC: Float?)

fun readBattery(context: Context): Battery? {
    val i = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)) ?: return null
    val level = i.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
    val scale = i.getIntExtra(BatteryManager.EXTRA_SCALE, 100)
    if (level < 0 || scale <= 0) return null
    val status = i.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
    val charging = status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL
    val temp = i.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE) // в десятых долях °C
    return Battery(level * 100 / scale, charging, if (temp == Int.MIN_VALUE) null else temp / 10f)
}

/** Таймер ключа ADB выключен (`0`) — иначе Android забудет ключ через 7 дней без подключений. */
fun adbTimeoutDisabled(context: Context): Boolean =
    Settings.Global.getString(context.contentResolver, "adb_allowed_connection_time") == "0"

/**
 * Отключение сна при снятии шлема. Работает из обычного приложения (проверено 01.11),
 * но сбрасывается при каждой перезагрузке — поэтому вызывается при каждом старте агента.
 */
object Sleep {
    @Volatile
    var disabled = false
        private set

    fun disable(context: Context) {
        context.sendBroadcast(Intent("com.oculus.vrpowermanager.prox_close"))
        disabled = true
        AgentLog.i("sleep disabled (prox_close)")
    }

    /** Вернуть обычное поведение: шлем засыпает, когда его снимают. */
    fun enable(context: Context) {
        context.sendBroadcast(Intent("com.oculus.vrpowermanager.automation_disable"))
        disabled = false
        AgentLog.i("sleep enabled (automation_disable)")
    }

    /** Сон входит в защиту: пока она включена, шлем не засыпает при снятии. */
    fun apply(context: Context, protected: Boolean) {
        if (protected) disable(context) else enable(context)
    }
}

/** Текущее приложение на переднем плане. Обновляет WatcherService. */
object CurrentApp {
    @Volatile
    var pkg: String? = null
        internal set

    /**
     * После перезапуска агента событий смены окна ещё не было — берём последнее
     * приложение из статистики использования (право выдаётся в provision.sh:
     * `appops set com.arena.agent GET_USAGE_STATS allow`). Без права — останется неизвестно.
     */
    fun initFromUsageStats(context: Context) {
        if (pkg != null) return
        try {
            val usm = context.getSystemService(UsageStatsManager::class.java)
            val now = System.currentTimeMillis()
            val events = usm.queryEvents(now - 24 * 3600_000L, now)
            val e = UsageEvents.Event()
            // На Quest панели Meta открываются на своих виртуальных экранах уже после игры,
            // поэтому «последнее открытое окно» — часто панель. Считаем, что сейчас открыто
            // (RESUMED без последующего PAUSED/STOPPED), и если среди этого есть игра — берём её.
            val open = LinkedHashSet<String>()
            var last: String? = null
            while (events.hasNextEvent()) {
                events.getNextEvent(e)
                if (e.packageName == VRUSB) continue
                when (e.eventType) {
                    UsageEvents.Event.ACTIVITY_RESUMED -> {
                        open.remove(e.packageName)
                        open.add(e.packageName)
                        last = e.packageName
                    }
                    UsageEvents.Event.ACTIVITY_PAUSED, UsageEvents.Event.ACTIVITY_STOPPED -> open.remove(e.packageName)
                }
            }
            val game = open.lastOrNull { !isSystemPackage(it) && it != context.packageName }
            val chosen = game ?: open.lastOrNull() ?: last
            if (chosen != null && pkg == null) {
                pkg = chosen
                AgentLog.i("current app from usage stats: $chosen (open: $open)")
            }
        } catch (e: Exception) {
            AgentLog.i("usage stats unavailable: ${e.message}")
        }
    }
}

/** Системные пакеты Meta и Android — это не игры. */
fun isSystemPackage(pkg: String): Boolean =
    listOf("com.oculus.", "com.meta.", "com.android.", "com.facebook.", "android").any { pkg.startsWith(it) }

/**
 * Пока включена охрана, долгое нажатие кнопки питания ничего не делает (вместо «выключить»).
 * Android берёт это поведение из Settings.Global (power_button_long_press: 0 — ничего),
 * писать туда можно с WRITE_SECURE_SETTINGS. Короткое нажатие (сон) так не отключить —
 * его обрабатывает AgentService: будит шлем обратно. Удержание ~10 с — аппаратное, не блокируется.
 */
object PowerLock {
    private val KEYS = listOf("power_button_long_press", "power_button_very_long_press")

    fun apply(context: Context, locked: Boolean) {
        try {
            for (key in KEYS) {
                if (locked) Settings.Global.putInt(context.contentResolver, key, 0)
                else Settings.Global.putString(context.contentResolver, key, null) // вернуть заводское
            }
            AgentLog.i("power button long press: ${if (locked) "blocked" else "default"}")
        } catch (e: SecurityException) {
            AgentLog.e("power lock: no WRITE_SECURE_SETTINGS", e)
        }
    }
}

/** События для статистики на сервере. AgentService подключает отправку при старте. */
object AgentEvents {
    @Volatile
    var sink: ((kind: String, payload: org.json.JSONObject) -> Unit)? = null

    fun emit(kind: String, payload: org.json.JSONObject = org.json.JSONObject()) {
        sink?.invoke(kind, payload)
    }
}

/**
 * Защита (функция 4 MVP): если игрок вышел из игры, через GUARD_DELAY_MS агент запускает её снова;
 * пока защита включена, шлем не засыпает при снятии и долгое нажатие питания не выключает его.
 * Хранится в настройках — переживает перезапуск агента.
 */
object Guard {
    private const val PREFS = "guard"
    private const val KEY = "pkg"
    private const val GUARD_DELAY_MS = 3000L
    private const val SUSPEND_AFTER_MS = 30_000L

    private val handler = Handler(Looper.getMainLooper())
    private var appContext: Context? = null
    private val relaunch = Runnable { check() }

    /**
     * Без связи с нашим сервером защита не работает: оператор не видит шлем и не может её снять.
     * Сразу после старта агента связи ещё нет — защита включится с первым подключением.
     */
    @Volatile
    private var suspended = true
    private val suspend = Runnable { applySuspended() }

    @Volatile
    private var holdUntil = 0L

    @Volatile
    private var sleepExpected = false

    /** Сейчас шлем усыпит оператор с дашборда: это не нажатие кнопки игроком. */
    fun expectSleep() {
        sleepExpected = true
    }

    /** true один раз: экран погас по команде оператора. */
    fun consumeExpectedSleep(): Boolean = sleepExpected.also { sleepExpected = false }

    /** Игра под защитой, если защита сейчас действует (включена и есть связь с сервером). */
    fun activePkg(context: Context): String? = if (suspended) null else get(context)

    /** Короткие обрывы защиту не снимают: она приостанавливается через SUSPEND_AFTER_MS без связи. */
    fun onServerConnection(context: Context, connected: Boolean) {
        appContext = context.applicationContext
        handler.removeCallbacks(suspend)
        if (!connected) {
            if (!suspended) handler.postDelayed(suspend, SUSPEND_AFTER_MS)
            return
        }
        if (!suspended) return
        suspended = false
        val pkg = get(context) ?: return
        AgentLog.i("guard: server connected, protection active for $pkg")
        applyEffects(context, on = true)
        onCurrentAppChanged(context)
    }

    private fun applySuspended() {
        val ctx = appContext ?: return
        suspended = true
        handler.removeCallbacks(relaunch)
        if (get(ctx) == null) return
        AgentLog.i("guard: no server connection, protection suspended")
        applyEffects(ctx, on = false)
    }

    private fun applyEffects(context: Context, on: Boolean) {
        PowerLock.apply(context, locked = on)
        Sleep.apply(context, protected = on)
    }

    /** Не возвращать игрока ближайшие ms: оператор сам закрывает или перезапускает игру. */
    fun hold(ms: Long) {
        holdUntil = SystemClock.elapsedRealtime() + ms
    }

    fun get(context: Context): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null)

    fun set(context: Context, pkg: String?) {
        appContext = context.applicationContext
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY, pkg).apply()
        AgentLog.i("guard: ${pkg ?: "off"}")
        applyEffects(context, on = pkg != null && !suspended)
        handler.removeCallbacks(relaunch)
        if (pkg != null) onCurrentAppChanged(context)
    }

    /** Вызывается при каждой смене текущего приложения. */
    fun onCurrentAppChanged(context: Context) {
        appContext = context.applicationContext
        handler.removeCallbacks(relaunch)
        val guarded = activePkg(context) ?: return
        val current = CurrentApp.pkg
        if (current == guarded || current == context.packageName) return
        handler.postDelayed(relaunch, GUARD_DELAY_MS)
    }

    private fun check() {
        val ctx = appContext ?: return
        val guarded = activePkg(ctx) ?: return
        if (CurrentApp.pkg == guarded) return
        val wait = holdUntil - SystemClock.elapsedRealtime()
        if (wait > 0) {
            handler.postDelayed(relaunch, wait)
            return
        }
        AgentLog.i("guard: current is ${CurrentApp.pkg}, relaunching $guarded")
        if (Launcher.launch(ctx, guarded)) {
            AgentEvents.emit("guard_relaunch", org.json.JSONObject().put("pkg", guarded).put("from", CurrentApp.pkg))
        }
        handler.postDelayed(relaunch, GUARD_DELAY_MS * 3) // если не запустилась — попробуем ещё
    }
}

/**
 * Accessibility-сервис: определяет текущее приложение по событиям смены окна.
 * Опрос списка окон не подходит: окно иммерсивной игры в нём не появляется (проверено).
 */
class WatcherService : AccessibilityService() {
    override fun onServiceConnected() {
        AgentLog.i("watcher connected")
        // Система сама поднимает Accessibility-сервис после загрузки и обновления —
        // запасной способ запустить агента, если BOOT_COMPLETED не пришёл
        AgentService.start(this)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        if (event.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return
        val pkg = event.packageName?.toString() ?: return
        if (pkg == VRUSB) return // системные окна разрешений отладки — не «текущее приложение»
        if (pkg != CurrentApp.pkg) {
            AgentLog.i("current app: ${CurrentApp.pkg} -> $pkg")
            CurrentApp.pkg = pkg
            Guard.onCurrentAppChanged(this)
        }
    }

    override fun onInterrupt() {}

}

private const val VRUSB = "com.oculus.os.vrusb"
