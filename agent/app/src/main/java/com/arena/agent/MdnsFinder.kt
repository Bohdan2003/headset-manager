package com.arena.agent

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.CopyOnWriteArrayList

/** Ищет порт беспроводной отладки: adbd объявляет его через mDNS как _adb-tls-connect._tcp. */
object MdnsFinder {
    private const val SERVICE_TYPE = "_adb-tls-connect._tcp"

    /**
     * Возвращает все найденные порты, свежие первыми.
     * Записей может быть несколько: после перезапуска отладки mDNS какое-то время
     * помнит старый порт («adb-...» и «adb-... (2)»), поэтому порты надо перебирать.
     */
    @Suppress("DEPRECATION") // resolveService устарел в API 34, но работает и проще для проверки
    fun findPorts(context: Context, timeoutMs: Long, settleMs: Long = 2_000): List<Int> {
        val nsd = context.getSystemService(NsdManager::class.java)
        val ports = CopyOnWriteArrayList<Int>()
        val first = CountDownLatch(1)
        val pending = java.util.concurrent.LinkedBlockingQueue<NsdServiceInfo>()

        val discovery = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) {
                AgentLog.i("mdns: discovery started")
            }

            override fun onServiceFound(info: NsdServiceInfo) {
                AgentLog.i("mdns: found ${info.serviceName}")
                pending.add(info)
            }

            override fun onServiceLost(info: NsdServiceInfo) {
                AgentLog.i("mdns: lost ${info.serviceName}")
            }

            override fun onDiscoveryStopped(serviceType: String) {}

            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {
                AgentLog.e("mdns: start failed, code=$errorCode")
                first.countDown()
            }

            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
        }

        nsd.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, discovery)

        // resolveService нельзя запускать параллельно — разрешаем записи по одной
        val end = System.currentTimeMillis() + timeoutMs
        var settleUntil = Long.MAX_VALUE
        while (System.currentTimeMillis() < minOf(end, settleUntil)) {
            val info = pending.poll(200, TimeUnit.MILLISECONDS) ?: continue
            val resolvedLatch = CountDownLatch(1)
            nsd.resolveService(info, object : NsdManager.ResolveListener {
                override fun onServiceResolved(resolved: NsdServiceInfo) {
                    AgentLog.i("mdns: resolved ${resolved.serviceName} -> ${resolved.host}:${resolved.port}")
                    if (resolved.port > 0 && resolved.port !in ports) ports.add(0, resolved.port)
                    resolvedLatch.countDown()
                }

                override fun onResolveFailed(failed: NsdServiceInfo, errorCode: Int) {
                    AgentLog.e("mdns: resolve failed ${failed.serviceName}, code=$errorCode")
                    resolvedLatch.countDown()
                }
            })
            resolvedLatch.await(5, TimeUnit.SECONDS)
            if (ports.isNotEmpty() && settleUntil == Long.MAX_VALUE) {
                settleUntil = System.currentTimeMillis() + settleMs
            }
        }
        try {
            nsd.stopServiceDiscovery(discovery)
        } catch (_: Exception) {
        }
        return ports.toList()
    }
}
