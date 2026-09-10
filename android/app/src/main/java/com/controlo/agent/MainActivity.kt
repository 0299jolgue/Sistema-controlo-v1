package com.controlo.agent
import android.app.Activity
import android.os.Bundle
import android.widget.TextView
class MainActivity:Activity(){override fun onCreate(b:Bundle?){super.onCreate(b);setContentView(TextView(this).apply{text="Sistema Controlo Agent\n\nEste agente só comunica após inscrição/autorização.\nA captura de ecrã requer consentimento oficial do Android.";textSize=18f;setPadding(32,48,32,48)}})}
