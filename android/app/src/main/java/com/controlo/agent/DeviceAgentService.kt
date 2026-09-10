package com.controlo.agent
import android.app.Service
import android.content.Intent
import android.os.IBinder
class DeviceAgentService:Service(){override fun onBind(i:Intent?):IBinder?=null;override fun onStartCommand(i:Intent?,f:Int,s:Int):Int{ /* TODO: WebSocket + heartbeat after enrollment */ return START_STICKY }}
