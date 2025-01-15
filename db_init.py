from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Float, DateTime 

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
    country_code = Column(String(5), nullable=False)
    contact_number = Column(String(20), nullable=False)
    location = Column(String(100), nullable=False)
    bio = Column(String, nullable=False)
    profile_image = Column(String, nullable=False)
    volunteer_credits = Column(Integer, nullable=True)

class ElderRecord(Base):
    __tablename__ = "elder_records"
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String(255), ForeignKey("users.email"), nullable=False, unique=True)  # Links to the elder's user record
    volunteer_email = Column(String(255), ForeignKey("users.email"), nullable=True, unique=True)  # Links to the assigned volunteer
    blood_pressure = Column(String, nullable=True)  # Example: "120/80"
    heart_rate = Column(String, nullable=True)  # Heart rate in beats per minute
    blood_sugar = Column(String, nullable=True)  # Blood sugar level in mg/dL
    oxygen_saturation = Column(String, nullable=True)  # Oxygen saturation as a percentage
    weight = Column(Float, nullable=True)  # Weight in kilograms
    height = Column(Float, nullable=True)  # Height in meters
    last_check_in = Column(DateTime(), nullable=True)  # Tracks the last check-in time
    status = Column(String(30), nullable=False) # current status of service

    # Relationships
    elder = relationship("UserModelDB", foreign_keys=[user_email], backref="elder_record")  # Elder relationship
    volunteer = relationship("UserModelDB", foreign_keys=[volunteer_email])  # Assigned volunteer relationship

Base.metadata.create_all(engine)