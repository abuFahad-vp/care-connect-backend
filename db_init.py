from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import \
    Column, Integer, String, Date, ForeignKey, DateTime, Text, Boolean
from datetime import datetime

engine = create_engine('sqlite:///amanah.db', echo=True, connect_args={"check_same_thread": False})
Base = declarative_base()


# Base User Model (shared attributes)
class UserModelDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    user_type = Column(String(10), nullable=False)  # 'elder' or 'volunteer'
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    dob = Column(Date(), nullable=False)
    contact_number = Column(String(20), nullable=False)
    location = Column(String(100), nullable=False)
    bio = Column(String, nullable=False)
    profile_image = Column(String, nullable=False)
    volunteer_credits = Column(Integer, nullable=True)


class ElderRecord(Base):
    __tablename__ = "elder_records"
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Text, nullable=True)
    user_email = Column(String(255), ForeignKey("users.email"), nullable=False, unique=True)
    volunteer_email = Column(String(255), ForeignKey("users.email"), nullable=True, unique=True)
    data = Column(String, nullable=True)
    # heart_rate = Column(String, nullable=True)
    # blood_sugar = Column(String, nullable=True)
    # oxygen_saturation = Column(String, nullable=True)
    # weight = Column(Float, nullable=True)
    # height = Column(Float, nullable=True)
    last_check_in = Column(DateTime(), nullable=True)
    status = Column(String(30), nullable=False)

    elder = relationship("UserModelDB", foreign_keys=[user_email], backref="elder_record")
    volunteer = relationship("UserModelDB", foreign_keys=[volunteer_email])


class Feedback(Base):
    __tablename__ = 'feedback'

    id = Column(Integer, primary_key=True, index=True)
    reporter_email = Column(String(255), ForeignKey('users.email'), nullable=False)
    reported_email = Column(String(255), ForeignKey('users.email'), nullable=False)
    feedback = Column(Text, nullable=False)
    feedback_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    status = Column(String, nullable=True)

    volunteer = relationship("UserModelDB", foreign_keys=[reporter_email])
    user = relationship("UserModelDB", foreign_keys=[reported_email])


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Text, nullable=False)
    sender = Column(Text, nullable=False)
    reciever = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(Text, default=False)


Base.metadata.create_all(engine)
