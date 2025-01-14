from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Date, Text 

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
    bio = Column(Text(), nullable=False)
    volunteer_credits = Column(Integer, nullable=True)

Base.metadata.create_all(engine)