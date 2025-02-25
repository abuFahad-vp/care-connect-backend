from db_init import UserModelDB, ElderRecord, ChatMessage
from model import UserBase, ElderStatus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from datetime import date, datetime

class DB:
    def __init__(self):
        self.engine = create_engine('sqlite:///amanah.db', echo=True, connect_args={"check_same_thread": False})
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        admin = UserModelDB(
            user_type="volunteer",
            full_name="Admin",
            email="admin@admin.com",
            password="$2b$12$HmFTxSN0Njh3a1kpMFirtOPJ6qxTAUBqzIlPz9B28fddbRnPdo96q", # admin123
            dob=date(1000,10,10),
            contact_number="123456789",
            bio="admin",
            profile_image="no profile",
            volunteer_credits=0,
            location="0.0,0.0",
        )
        if self.session.query(UserModelDB).filter(UserModelDB.email == "admin@admin.com").first() is None:
            self.session.add(admin)
            self.session.commit()

    def get_unassigned_volunteers(self):
        stmt = select(UserModelDB).join(ElderRecord, UserModelDB.email == ElderRecord.volunteer_email, isouter=True).filter(
            UserModelDB.user_type == "volunteer",  # Only include volunteers
            (ElderRecord.volunteer_email == None) |  # Volunteer is not assigned
            (ElderRecord.status != "assigned")  # Volunteer is not assigned in ElderRecord
        )
        result = self.session.execute(stmt).scalars().all()
        return result

    def get_elder_record_by_email(self, email: str, user_type: str):
        if user_type == "elder":
            stmt = select(ElderRecord).where(ElderRecord.user_email == email)
        elif user_type == "volunteer":
            stmt = select(ElderRecord).where(ElderRecord.volunteer_email == email)
        else:
            raise ValueError("Invalid user type. Must be 'elder' or 'volunteer'.")

        result = self.session.execute(stmt).scalars().first()
        return result

    def get_user_by_email(self, email: str):
        stmt = select(UserModelDB).where(UserModelDB.email == email)
        result = self.session.execute(stmt).scalars().first()
        return result

    def create_empty_elder_record(self, user: UserBase):
        new_record = ElderRecord(
            user_email=user.email,
            status = ElderStatus.not_assigned,
            volunteer_email=None,
            service_id=None,
            data = None,
            # blood_pressure=None,  
            # heart_rate=None,  
            # blood_sugar=None,  
            # oxygen_saturation=None,  
            # weight=None,  
            # height=None,  
            last_check_in=None,  
        )
        self.session.add(new_record)
        self.session.commit()
        return new_record

    def from_responseModel_to_dbModel(user: UserBase) -> UserModelDB:
        return UserModelDB(
            user_type=user.user_type,
            full_name=user.full_name,
            email=user.email,
            password=user.password,
            dob=user.dob,
            contact_number=user.contact_number,
            bio=user.bio,
            profile_image=user.profile_image,
            volunteer_credits=user.volunteer_credits,
            location=user.location
        )

    def from_DBModel_to_responseModel(self, user: UserModelDB) -> UserBase:
        return UserBase(
            user_type=user.user_type,
            full_name=user.full_name,
            email=user.email,
            password=user.password,
            dob=user.dob,
            contact_number=user.contact_number,
            bio=user.bio,
            profile_image=user.profile_image,
            location=user.location,
            volunteer_credits=user.volunteer_credits
        )

    def add_user(self, user: UserBase):
        new_user = DB.from_responseModel_to_dbModel(user)
        self.session.add(new_user)
        self.session.commit()

    def add_message(self, response: dict):
        message = ChatMessage(
            content=response["content"],
            service_id=response["service_id"],
            sender=response["sender"],
            reciever=response["reciever"],
            status=response["status"]
        )
        self.session.add(message)
        self.session.commit()
