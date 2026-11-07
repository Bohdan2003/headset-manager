package com.arena.agent

import android.content.Context
import android.util.Base64
import java.io.File
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.security.spec.PKCS8EncodedKeySpec

/**
 * Ключ, которому шлем доверяет (разрешён по USB с «Always allow").
 * Лежит в filesDir агента (доступен только самому приложению).
 * TODO: шифровать ключом из Android Keystore.
 */
object AdbKey {
    private const val KEY_FILE = "adbkey.der"
    private const val CERT_FILE = "adbcert.der"

    class Loaded(val privateKey: PrivateKey, val certificate: X509Certificate)

    /** Сохраняет ключ и возвращает SHA-256 отпечаток открытого ключа (первые 16 hex). */
    fun save(context: Context, keyB64: String, certB64: String): String {
        val keyDer = Base64.decode(keyB64, Base64.DEFAULT)
        val certDer = Base64.decode(certB64, Base64.DEFAULT)
        // Проверяем, что всё разбирается, до записи на диск
        val loaded = parse(keyDer, certDer)
        File(context.filesDir, KEY_FILE).writeBytes(keyDer)
        File(context.filesDir, CERT_FILE).writeBytes(certDer)
        return fingerprint(loaded)
    }

    fun load(context: Context): Loaded? {
        val k = File(context.filesDir, KEY_FILE)
        val c = File(context.filesDir, CERT_FILE)
        if (!k.exists() || !c.exists()) return null
        return parse(k.readBytes(), c.readBytes())
    }

    fun fingerprint(loaded: Loaded): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(loaded.certificate.publicKey.encoded)
        return digest.take(8).joinToString("") { "%02x".format(it) }
    }

    private fun parse(keyDer: ByteArray, certDer: ByteArray): Loaded {
        val key = KeyFactory.getInstance("RSA").generatePrivate(PKCS8EncodedKeySpec(keyDer))
        val cert = CertificateFactory.getInstance("X.509")
            .generateCertificate(certDer.inputStream()) as X509Certificate
        return Loaded(key, cert)
    }
}
