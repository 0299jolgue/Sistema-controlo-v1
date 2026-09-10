package com.controlo.agent
import org.json.JSONObject
class AgentRepository(private val serverUrl:String){fun enrollmentPayload(token:String,id:String,model:String,androidVersion:String)=JSONObject().apply{put("token",token);put("internal_id",id);put("name",model);put("manufacturer",android.os.Build.MANUFACTURER);put("model",model);put("android_version",androidVersion);put("agent_version","1.0.0")};fun discoverServer()=serverUrl.trimEnd('/')}
