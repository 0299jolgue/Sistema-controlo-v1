from datetime import datetime,timezone
from sqlalchemy import String,Integer,Boolean,DateTime,Text,ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from .db import Base
def now(): return datetime.now(timezone.utc)
class Device(Base):
 __tablename__="devices"; id:Mapped[int]=mapped_column(primary_key=True); internal_id:Mapped[str]=mapped_column(String(64),unique=True,index=True); name:Mapped[str]=mapped_column(String(120),default="Android device"); manufacturer:Mapped[str]=mapped_column(String(120),default="Unknown"); model:Mapped[str]=mapped_column(String(120),default="Unknown"); android_version:Mapped[str]=mapped_column(String(60),default="Unknown"); agent_version:Mapped[str]=mapped_column(String(60),default="0.1.0"); battery:Mapped[int]=mapped_column(Integer,default=0); network:Mapped[str]=mapped_column(String(80),default="Unknown"); ip_address:Mapped[str]=mapped_column(String(64),default=""); online:Mapped[bool]=mapped_column(Boolean,default=False); authorized:Mapped[bool]=mapped_column(Boolean,default=True); device_token_hash:Mapped[str]=mapped_column(String(128),default=""); last_seen:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class EnrollmentToken(Base):
 __tablename__="enrollment_tokens"; id:Mapped[int]=mapped_column(primary_key=True); token:Mapped[str]=mapped_column(String(64),unique=True,index=True); expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True)); used:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Command(Base):
 __tablename__="commands"; id:Mapped[int]=mapped_column(primary_key=True); device_id:Mapped[int]=mapped_column(ForeignKey("devices.id")); type:Mapped[str]=mapped_column(String(80)); payload:Mapped[str]=mapped_column(Text,default="{}"); status:Mapped[str]=mapped_column(String(30),default="Pending"); response:Mapped[str]=mapped_column(Text,default=""); error:Mapped[str]=mapped_column(Text,default=""); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now); updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class LogEvent(Base):
 __tablename__="logs"; id:Mapped[int]=mapped_column(primary_key=True); device_id:Mapped[int|None]=mapped_column(Integer,nullable=True); event_type:Mapped[str]=mapped_column(String(80)); description:Mapped[str]=mapped_column(Text); status:Mapped[str]=mapped_column(String(30),default="info"); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Message(Base):
 __tablename__="messages"; id:Mapped[int]=mapped_column(primary_key=True); device_id:Mapped[int]=mapped_column(ForeignKey("devices.id")); body:Mapped[str]=mapped_column(Text); status:Mapped[str]=mapped_column(String(30),default="Pending"); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Notification(Base):
 __tablename__="notifications"; id:Mapped[int]=mapped_column(primary_key=True); device_id:Mapped[int]=mapped_column(ForeignKey("devices.id")); app_name:Mapped[str]=mapped_column(String(120),default=""); title:Mapped[str]=mapped_column(String(200),default=""); content:Mapped[str]=mapped_column(Text,default=""); status:Mapped[str]=mapped_column(String(30),default="New"); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ApkBuild(Base):
 __tablename__="apk_builds"; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String(120),default="Android Agent"); version:Mapped[str]=mapped_column(String(60),default="1.0.0"); status:Mapped[str]=mapped_column(String(30),default="Waiting"); artifact_path:Mapped[str]=mapped_column(String(240),default=""); created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class AppSetting(Base):
 __tablename__="settings"; id:Mapped[int]=mapped_column(primary_key=True); key:Mapped[str]=mapped_column(String(120),unique=True,index=True); value:Mapped[str]=mapped_column(Text,default="")
