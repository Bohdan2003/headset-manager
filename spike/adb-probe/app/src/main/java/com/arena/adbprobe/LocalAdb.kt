package com.arena.adbprobe

import java.io.Closeable
import java.io.DataInputStream
import java.io.OutputStream
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.Principal
import java.security.PrivateKey
import java.security.cert.X509Certificate
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLEngine
import javax.net.ssl.SSLSocket
import javax.net.ssl.X509ExtendedKeyManager
import javax.net.ssl.X509ExtendedTrustManager

/**
 * Минимальный клиент протокола ADB для беспроводной отладки (TLS).
 *
 * Как устроено подключение:
 *  1. По обычному TCP шлём CNXN.
 *  2. adbd отвечает STLS — «переходим на TLS». Отвечаем STLS.
 *  3. TLS 1.3 рукопожатие. adbd проверяет наш клиентский сертификат:
 *     его открытый ключ должен быть в /data/misc/adb/adb_keys.
 *  4. adbd присылает CNXN — соединение готово.
 *  5. Каждая команда: OPEN "shell:<cmd>" → OKAY → WRTE (вывод, на каждый отвечаем OKAY) → CLSE.
 */
class LocalAdb(private val key: AdbKey.Loaded) : Closeable {

    private class Message(val cmd: Int, val arg0: Int, val arg1: Int, val data: ByteArray)

    private lateinit var socket: Socket
    private lateinit var input: DataInputStream
    private lateinit var output: OutputStream
    private var nextLocalId = 1

    fun connect(host: String, port: Int, timeoutMs: Int = 10_000) {
        val plain = Socket()
        plain.connect(InetSocketAddress(host, port), timeoutMs)
        plain.soTimeout = timeoutMs

        write(plain.getOutputStream(), A_CNXN, VERSION, MAX_DATA, "host::\u0000".toByteArray())
        val first = read(DataInputStream(plain.getInputStream()))
        when (first.cmd) {
            A_STLS -> {
                write(plain.getOutputStream(), A_STLS, STLS_VERSION, 0, ByteArray(0))
                val tls = upgradeToTls(plain, host, port)
                socket = tls
                input = DataInputStream(tls.inputStream)
                output = tls.outputStream
            }
            A_AUTH -> throw IllegalStateException("adbd asked for RSA AUTH (not a TLS port?)")
            else -> throw IllegalStateException("unexpected first message ${name(first.cmd)}")
        }

        // После TLS adbd присылает CNXN
        while (true) {
            val m = read(input)
            if (m.cmd == A_CNXN) {
                ProbeLog.i("adb: connected, banner=\"${String(m.data).trimEnd('\u0000').take(120)}\"")
                return
            }
            ProbeLog.i("adb: skip ${name(m.cmd)} before CNXN")
        }
    }

    /** Выполняет shell-команду и возвращает её вывод. */
    fun shell(command: String): String {
        val localId = nextLocalId++
        write(output, A_OPEN, localId, 0, "shell:$command\u0000".toByteArray())
        var remoteId = 0
        val out = StringBuilder()
        while (true) {
            val m = read(input)
            when (m.cmd) {
                A_OKAY -> remoteId = m.arg0
                A_WRTE -> {
                    remoteId = m.arg0
                    out.append(String(m.data))
                    write(output, A_OKAY, localId, remoteId, ByteArray(0))
                }
                A_CLSE -> {
                    write(output, A_CLSE, localId, remoteId, ByteArray(0))
                    return out.toString()
                }
                else -> ProbeLog.i("adb: unexpected ${name(m.cmd)} during shell")
            }
        }
    }

    override fun close() {
        try {
            socket.close()
        } catch (_: Exception) {
        }
    }

    private fun upgradeToTls(plain: Socket, host: String, port: Int): SSLSocket {
        val ctx = SSLContext.getInstance("TLSv1.3")
        ctx.init(arrayOf(ClientKeyManager(key)), arrayOf(AcceptAllTrustManager()), null)
        val tls = ctx.socketFactory.createSocket(plain, host, port, true) as SSLSocket
        tls.enabledProtocols = arrayOf("TLSv1.3")
        tls.useClientMode = true
        tls.startHandshake()
        ProbeLog.i("adb: TLS handshake ok, ${tls.session.protocol} ${tls.session.cipherSuite}")
        return tls
    }

    private fun read(input: DataInputStream): Message {
        val header = ByteArray(24)
        input.readFully(header)
        val b = ByteBuffer.wrap(header).order(ByteOrder.LITTLE_ENDIAN)
        val cmd = b.int
        val arg0 = b.int
        val arg1 = b.int
        val len = b.int
        b.int // crc — с версии 0x01000001 не проверяется
        val magic = b.int
        require(magic == cmd.inv()) { "bad magic for ${name(cmd)}" }
        val data = ByteArray(len)
        input.readFully(data)
        return Message(cmd, arg0, arg1, data)
    }

    private fun write(out: OutputStream, cmd: Int, arg0: Int, arg1: Int, data: ByteArray) {
        val b = ByteBuffer.allocate(24 + data.size).order(ByteOrder.LITTLE_ENDIAN)
        b.putInt(cmd).putInt(arg0).putInt(arg1).putInt(data.size)
        b.putInt(data.sumOf { it.toInt() and 0xff })
        b.putInt(cmd.inv())
        b.put(data)
        out.write(b.array())
        out.flush()
    }

    /** Отдаёт наш ключ и сертификат как клиентский сертификат TLS. */
    private class ClientKeyManager(private val key: AdbKey.Loaded) : X509ExtendedKeyManager() {
        override fun chooseClientAlias(keyType: Array<out String>?, issuers: Array<out Principal>?, socket: Socket?) = ALIAS
        override fun chooseEngineClientAlias(keyType: Array<out String>?, issuers: Array<out Principal>?, engine: SSLEngine?) = ALIAS
        override fun getClientAliases(keyType: String?, issuers: Array<out Principal>?) = arrayOf(ALIAS)
        override fun getCertificateChain(alias: String?) = arrayOf(key.certificate)
        override fun getPrivateKey(alias: String?): PrivateKey = key.privateKey
        override fun getServerAliases(keyType: String?, issuers: Array<out Principal>?) = null
        override fun chooseServerAlias(keyType: String?, issuers: Array<out Principal>?, socket: Socket?) = null

        companion object {
            const val ALIAS = "adb"
        }
    }

    /** adbd использует самоподписанный сертификат; подключаемся только к 127.0.0.1. */
    private class AcceptAllTrustManager : X509ExtendedTrustManager() {
        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?, socket: Socket?) {}
        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?, engine: SSLEngine?) {}
        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?, socket: Socket?) {}
        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?, engine: SSLEngine?) {}
        override fun getAcceptedIssuers() = arrayOf<X509Certificate>()
    }

    companion object {
        private const val A_CNXN = 0x4e584e43
        private const val A_OPEN = 0x4e45504f
        private const val A_OKAY = 0x59414b4f
        private const val A_CLSE = 0x45534c43
        private const val A_WRTE = 0x45545257
        private const val A_AUTH = 0x48545541
        private const val A_STLS = 0x534c5453
        private const val VERSION = 0x01000001
        private const val STLS_VERSION = 0x01000000
        private const val MAX_DATA = 256 * 1024

        private fun name(cmd: Int): String {
            val b = ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(cmd).array()
            return String(b)
        }
    }
}
