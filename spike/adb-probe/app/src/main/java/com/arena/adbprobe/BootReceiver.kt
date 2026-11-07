package com.arena.adbprobe

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        ProbeLog.init(context)
        ProbeLog.i("BOOT_COMPLETED received")
        ProbeService.start(context, "boot")
    }
}
