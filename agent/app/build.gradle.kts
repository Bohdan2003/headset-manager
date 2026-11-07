plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.arena.agent"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.arena.agent"
        minSdk = 29
        // 32, а не 34: не нужны требования Android 14 к типам foreground-сервисов
        targetSdk = 32
        versionCode = 21
        versionName = "0.11.3"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    lint {
        // WRITE_SECURE_SETTINGS — системное право, выдаём через pm grant
        abortOnError = false
        checkReleaseBuilds = false
    }
}

dependencies {
    // WebSocket-клиент: в Android своего нет
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
}
