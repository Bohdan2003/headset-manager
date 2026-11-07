package com.arena.agent

import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.BroadcastReceiver
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.Network
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.provider.Settings
import org.json.JSONObject

/**
 * Главный сервис агента. Живёт всё время (foreground), стартует при загрузке шлема.
 * Держит соединение с сервером, шлёт heartbeat, поднимает локальный ADB.
 */
class AgentService : Service() {

    private val thread = HandlerThread("agent").apply { start() }
    private val handler = Handler(thread.looper)

    private lateinit var config: AgentConfig
    private lateinit var connection: ServerConnection
    private lateinit var adb: AdbManager
    private lateinit var executor: CommandExecutor
    private var heartbeatMs = 5_000L

    /** Заряд контроллеров меняется медленно — раз в минуту хватает. */
    private val controllersThread = java.util.concurrent.Executors.newSingleThreadScheduledExecutor { Thread(it, "controllers") }

    private val heartbeat = object : Runnable {
        override fun run() {
            sendHeartbeat()
            handler.postDelayed(this, heartbeatMs)
        }
    }

    private val network = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(net: Network) {
            AgentLog.i("network available")
            handler.post {
                connection.reconnectNow()
                adb.refresh() // после обрыва Wi-Fi Android выключает беспроводную отладку
            }
        }

        override fun onLost(net: Network) {
            AgentLog.i("network lost")
            adb.networkLost()
        }
    }

    /**
     * Короткое нажатие кнопки питания усыпляет шлем, и это нельзя запретить настройкой.
     * Игра при этом теряет связь со своим сервером, поэтому под защитой не просто будим шлем,
     * а перезапускаем игру.
     */
    private val screenOff = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            handler.post { sendHeartbeat() }
            if (intent.action != Intent.ACTION_SCREEN_OFF || Guard.consumeExpectedSleep()) return
            val guarded = Guard.activePkg(context) ?: return
            AgentLog.i("screen off while protecting $guarded — restarting the game")
            executor.restartAfterPowerPress(guarded)
        }
    }

    /** Пауэрбанк вставили или вынули — сообщить сразу, не ждать очередной heartbeat. */
    private val power = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            handler.postDelayed({ sendHeartbeat() }, 1000) // статус зарядки обновляется не мгновенно
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    @SuppressLint("HardwareIds")
    override fun onCreate() {
        super.onCreate()
        startForeground(NOTIFICATION_ID, notification())
        AgentLog.i("agent ${BuildConfigCompat.version(this)} started")

        config = AgentConfig(this)
        Sleep.apply(this, protected = false) // до связи с сервером защита не действует
        CurrentApp.initFromUsageStats(this)
        adb = AdbManager(this) { handler.post { sendHeartbeat() } }
        executor = CommandExecutor(this, adb)
        connection = ServerConnection(
            config = config,
            handler = handler,
            agentVersion = BuildConfigCompat.version(this),
            androidId = Settings.Secure.getString(contentResolver, Settings.Secure.ANDROID_ID),
            listener = object : ServerConnection.Listener {
                override fun onWelcome(heartbeatIntervalS: Int) {
                    heartbeatMs = heartbeatIntervalS.coerceIn(1, 60) * 1000L
                    handler.removeCallbacks(heartbeat)
                    handler.post(heartbeat) // первый heartbeat сразу
                    Guard.onServerConnection(this@AgentService, connected = true)
                    connection.send(JSONObject().put("type", "apps").put("apps", installedApps(this@AgentService)))
                }

                override fun onCommand(msg: JSONObject) {
                    executor.execute(msg) { ack ->
                        handler.post {
                            connection.send(ack)
                            sendHeartbeat() // состояние изменилось — сообщить сразу, не ждать 5 с
                        }
                    }
                }

                override fun onClosed() {
                    handler.removeCallbacks(heartbeat)
                    Guard.onServerConnection(this@AgentService, connected = false)
                }
            },
        )

        AgentEvents.sink = { kind, payload ->
            handler.post { connection.send(JSONObject().put("type", "event").put("kind", kind).put("payload", payload)) }
        }
        RebootHook.beforeReboot = {
            // Закрыть соединение самим — иначе сервер заметит офлайн только через ~15 с тишины
            handler.post { connection.stop() }
        }
        RebootHook.rebootFailed = { handler.post { connection.start() } }

        controllersThread.scheduleWithFixedDelay(
            { runCatching { Controllers.refresh(this, adb) }.onFailure { AgentLog.e("controllers failed", it) } },
            5, 60, java.util.concurrent.TimeUnit.SECONDS,
        )
        registerReceiver(
            screenOff,
            IntentFilter().apply {
                addAction(Intent.ACTION_SCREEN_OFF)
                addAction(Intent.ACTION_SCREEN_ON)
            },
        )
        registerReceiver(
            power,
            IntentFilter().apply {
                addAction(Intent.ACTION_POWER_CONNECTED)
                addAction(Intent.ACTION_POWER_DISCONNECTED)
            },
        )
        PowerLock.apply(this, locked = false)

        getSystemService(ConnectivityManager::class.java).registerDefaultNetworkCallback(network, handler)
        handler.post { connection.start() }
        adb.refresh()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.getBooleanExtra(EXTRA_RESTART, false) == true) {
            AgentLog.i("config changed, reconnecting")
            handler.post {
                connection.stop()
                connection.start()
            }
            adb.refresh()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        controllersThread.shutdownNow()
        unregisterReceiver(screenOff)
        unregisterReceiver(power)
        getSystemService(ConnectivityManager::class.java).unregisterNetworkCallback(network)
        handler.post { connection.stop() }
        thread.quitSafely()
        super.onDestroy()
    }

    private fun sendHeartbeat() {
        val battery = readBattery(this)
        val msg = JSONObject()
            .put("type", "heartbeat")
            .put("battery", battery?.level ?: 0)
            .put("charging", battery?.charging ?: false)
            .put("temp", battery?.tempC?.toDouble() ?: JSONObject.NULL)
            .put("currentPkg", CurrentApp.pkg ?: JSONObject.NULL)
            .put("adb", adb.status)
            .put("sleepDisabled", Sleep.disabled)
            .put("adbTimeoutDisabled", adbTimeoutDisabled(this))
            .put("guardPkg", Guard.get(this) ?: JSONObject.NULL)
            .put("screenOn", getSystemService(android.os.PowerManager::class.java).isInteractive)
            .put("controllers", Controllers.last ?: JSONObject.NULL)
        connection.send(msg)
    }

    private fun notification(): Notification {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL, "Arena Agent", NotificationManager.IMPORTANCE_LOW))
        return Notification.Builder(this, CHANNEL)
            .setContentTitle("Arena Agent")
            .setContentText("This headset is managed by the arena")
            .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
            .build()
    }

    companion object {
        private const val CHANNEL = "agent"
        private const val NOTIFICATION_ID = 1
        private const val EXTRA_RESTART = "restart"

        fun start(context: Context, restart: Boolean = false) {
            context.startForegroundService(
                Intent(context, AgentService::class.java).putExtra(EXTRA_RESTART, restart)
            )
        }
    }
}

private object BuildConfigCompat {
    fun version(context: Context): String =
        context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: "?"
}
