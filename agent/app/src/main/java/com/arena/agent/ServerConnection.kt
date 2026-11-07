package com.arena.agent

import android.os.Handler
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Постоянное соединение с сервером по WebSocket.
 * Первое сообщение — hello; после welcome соединение считается открытым.
 * При обрыве переподключается с нарастающей паузой: 1, 2, 5, 10, 20, 30 с.
 * Все колбэки приходят в поток handler.
 */
class ServerConnection(
    private val config: AgentConfig,
    private val handler: Handler,
    private val agentVersion: String,
    private val androidId: String?,
    private val listener: Listener,
) {
    interface Listener {
        fun onWelcome(heartbeatIntervalS: Int)
        fun onCommand(msg: JSONObject)
        fun onClosed()
    }

    // ping раз в 20 с: если сервер пропал без закрытия соединения (выключили Wi-Fi), OkHttp это заметит
    private val client = OkHttpClient.Builder().pingInterval(20, TimeUnit.SECONDS).build()
    private var ws: WebSocket? = null
    private var attempt = 0
    private var stopped = false

    @Volatile
    var isOpen = false
        private set

    private val reconnect = Runnable { connect() }

    fun start() {
        stopped = false
        connect()
    }

    fun stop() {
        stopped = true
        handler.removeCallbacks(reconnect)
        ws?.close(1000, "agent stopped")
        ws = null
        isOpen = false
    }

    /** Сеть появилась — не ждать окончания паузы. */
    fun reconnectNow() {
        if (isOpen || stopped) return
        attempt = 0
        handler.removeCallbacks(reconnect)
        handler.post(reconnect)
    }

    fun send(json: JSONObject): Boolean = isOpen && (ws?.send(json.toString()) ?: false)

    private fun connect() {
        handler.removeCallbacks(reconnect)
        ws?.cancel()
        val base = config.serverUrl
        if (base == null || !config.isProvisioned) {
            AgentLog.i("server: not provisioned, waiting for PROVISION")
            return
        }
        val url = base.trimEnd('/').replaceFirst(Regex("^http"), "ws") + "/agent"
        AgentLog.i("server: connecting to $url (attempt ${attempt + 1})")
        ws = client.newWebSocket(Request.Builder().url(url).build(), Callbacks())
    }

    private fun scheduleReconnect(slow: Boolean) {
        if (stopped) return
        val delayS = if (slow) 60L else BACKOFF_S[minOf(attempt, BACKOFF_S.lastIndex)]
        attempt++
        AgentLog.i("server: reconnect in ${delayS}s")
        handler.postDelayed(reconnect, delayS * 1000)
    }

    private inner class Callbacks : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            val hello = JSONObject()
                .put("type", "hello")
                .put("headsetId", config.headsetId)
                .put("token", config.token)
                .put("agentVersion", agentVersion)
                .put("androidId", androidId ?: JSONObject.NULL)
            webSocket.send(hello.toString())
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            handler.post {
                if (webSocket !== ws) return@post
                val msg = try {
                    JSONObject(text)
                } catch (e: Exception) {
                    AgentLog.e("server: bad message", e)
                    return@post
                }
                when (msg.optString("type")) {
                    "welcome" -> {
                        attempt = 0
                        isOpen = true
                        AgentLog.i("server: connected")
                        listener.onWelcome(msg.optInt("heartbeatIntervalS", 5))
                    }
                    "command" -> if (isOpen) listener.onCommand(msg)
                    else -> AgentLog.i("server: unhandled message type=${msg.optString("type")}")
                }
            }
        }

        override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
            webSocket.close(code, null)
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            handler.post { onDisconnected(webSocket, "closed code=$code", slow = code == CLOSE_UNAUTHORIZED) }
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            handler.post { onDisconnected(webSocket, "failure ${t.javaClass.simpleName}: ${t.message}", slow = false) }
        }
    }

    private fun onDisconnected(webSocket: WebSocket, why: String, slow: Boolean) {
        if (webSocket !== ws) return
        val wasOpen = isOpen
        isOpen = false
        ws = null
        AgentLog.i("server: disconnected ($why)" + if (slow) " — token rejected, re-provision needed" else "")
        if (wasOpen) listener.onClosed()
        scheduleReconnect(slow)
    }

    private companion object {
        val BACKOFF_S = longArrayOf(1, 2, 5, 10, 20, 30)
        const val CLOSE_UNAUTHORIZED = 4401
    }
}
