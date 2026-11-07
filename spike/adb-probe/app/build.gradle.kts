plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.arena.adbprobe"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.arena.adbprobe"
        minSdk = 29
        // 32, а не 34: для проверки не нужны требования Android 14 к типам foreground-сервисов
        targetSdk = 32
        versionCode = 1
        versionName = "0.1"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    lint {
        // WRITE_SECURE_SETTINGS — системное право, lint на него ругается; выдаём через pm grant
        abortOnError = false
        checkReleaseBuilds = false
    }
}
