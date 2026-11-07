package com.arena.adbprobe

import android.accessibilityservice.AccessibilityService
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo

/**
 * Accessibility-сервис тестового приложения. Проверяет три вещи:
 *  1. Какое приложение сейчас на переднем плане (для «текущая игра»).
 *     Берём из событий TYPE_WINDOW_STATE_CHANGED: окно иммерсивной игры в списке окон
 *     Accessibility не появляется (проверено), а событие о нём приходит.
 *  2. Возврат в игру: если охраняемая игра потеряла фокус дольше GUARD_DELAY_MS — запустить её снова.
 *  3. Повторная попытка нажать «Allow» в окне беспроводной отладки — опросом окон по таймеру,
 *     раз события от этого окна не приходят.
 *
 * Важно: окно разрешения USB-отладки живёт в том же пакете com.oculus.os.vrusb.
 * Его нажимать НЕЛЬЗЯ — иначе любой, кто подключит кабель, получит доступ к шлему.
 * Поэтому проверяем заголовок окна и жмём только при совпадении.
 *
 * Имя класса оставлено прежним, чтобы не перевключать сервис в настройках шлема.
 */
class DialogClickerService : AccessibilityService() {

    private val handler = Handler(Looper.getMainLooper())
    private var lastClickAt = 0L
    private var focusedPkg: String? = null   // по опросу окон — только для журнала
    private var currentPkg: String? = null   // по событиям — это и есть «текущее приложение»
    private var currentSince = 0L

    private val poll = object : Runnable {
        override fun run() {
            try {
                pollWindows()
            } catch (e: Exception) {
                ProbeLog.e("a11y: poll failed", e)
            }
            handler.postDelayed(this, POLL_MS)
        }
    }

    override fun onServiceConnected() {
        ProbeLog.init(this)
        ProbeLog.i("a11y: service connected")
        handler.post(poll)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        if (event.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return
        val pkg = event.packageName?.toString() ?: return
        ProbeLog.i(
            "a11y: event STATE_CHANGED pkg=$pkg class=${event.className} " +
                "display=${if (Build.VERSION.SDK_INT >= 30) event.displayId else -1}"
        )
        if (pkg == VRUSB) {
            clickWirelessDialog("event")
            return
        }
        if (pkg != currentPkg) {
            ProbeLog.i("a11y: current ${currentPkg ?: "-"} -> $pkg")
            currentPkg = pkg
            currentSince = SystemClock.elapsedRealtime()
        }
    }

    /** Раз в POLL_MS смотрим окна: кто в фокусе, и нет ли окна беспроводной отладки. */
    private fun pollWindows() {
        val windows = allWindows()

        val focused = windows.firstOrNull { it.isFocused } ?: windows.firstOrNull { it.isActive }
        val pkg = focused?.root?.packageName?.toString()
        if (pkg != focusedPkg) {
            ProbeLog.i(
                "a11y: focus ${focusedPkg ?: "-"} -> ${pkg ?: "-"} " +
                    "(type=${focused?.type}, windows=${windows.size}, " +
                    "pkgs=${windows.mapNotNull { it.root?.packageName }.distinct()})"
            )
            focusedPkg = pkg
        }

        if (windows.any { it.root?.packageName?.toString() == VRUSB }) clickWirelessDialog("poll")

        guardGame()
    }

    /** Функция 4 MVP: вернуть игрока в игру, если он из неё вышел. */
    private fun guardGame() {
        val guarded = Guard.get(this) ?: return
        val current = currentPkg ?: return
        if (current == guarded || current == packageName) return
        if (SystemClock.elapsedRealtime() - currentSince < GUARD_DELAY_MS) return
        ProbeLog.i("guard: current is $current, relaunching $guarded")
        Launcher.launch(this, guarded, "guard")
        currentSince = SystemClock.elapsedRealtime() // не чаще раза в GUARD_DELAY_MS
    }

    private fun allWindows(): List<AccessibilityWindowInfo> =
        if (Build.VERSION.SDK_INT >= 30) {
            val all = windowsOnAllDisplays
            (0 until all.size()).flatMap { all.valueAt(it) }
        } else {
            windows
        }

    private fun clickWirelessDialog(source: String) {
        if (SystemClock.elapsedRealtime() - lastClickAt < 1500) return
        val roots = mutableListOf<AccessibilityNodeInfo>()
        rootInActiveWindow?.let { roots += it }
        allWindows().forEach { w -> w.root?.let { roots += it } }
        for (root in roots) {
            if (tryClick(root, source)) {
                lastClickAt = SystemClock.elapsedRealtime()
                return
            }
        }
    }

    private fun tryClick(root: AccessibilityNodeInfo, source: String): Boolean {
        if (root.packageName?.toString() != VRUSB) return false
        val title = root.findAccessibilityNodeInfosByViewId("android:id/alertTitle")
            .firstOrNull()?.text?.toString() ?: return false
        if (!title.contains("wireless debugging", ignoreCase = true)) {
            ProbeLog.i("a11y: vrusb dialog ignored, title=\"$title\"")
            return false
        }
        val allow = root.findAccessibilityNodeInfosByViewId("android:id/button1").firstOrNull()
        if (allow == null) {
            ProbeLog.i("a11y: title matched but button1 not found")
            return false
        }
        val ok = allow.performAction(AccessibilityNodeInfo.ACTION_CLICK)
        ProbeLog.i("a11y: [$source] clicked \"${allow.text}\" in \"$title\" -> $ok")
        return ok
    }

    override fun onInterrupt() {}

    override fun onDestroy() {
        handler.removeCallbacks(poll)
        super.onDestroy()
    }

    companion object {
        const val VRUSB = "com.oculus.os.vrusb"
        private const val POLL_MS = 1000L
        private const val GUARD_DELAY_MS = 3000L
    }
}
