from db_init import UserModelDB, ElderRecord, ChatMessage
from model import UserBase, ElderStatus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from datetime import date
from institutions import captain_institutions
import bcrypt


class DB:

    def __init__(self):
        self.engine = create_engine(
            'sqlite:///amanah.db',
            echo=True,
            connect_args={"check_same_thread": False})

        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        print("institution: ", captain_institutions)

        for email, (name, password) in captain_institutions.items():

            pwd_bytes = password.encode('utf-8')
            gen_salt = bcrypt.gensalt()
            new_pass = bcrypt.hashpw(pwd_bytes, gen_salt).decode('utf-8')

            captian = UserModelDB(
                user_type="volunteer",
                full_name="Captian",
                email=email,
                password=new_pass,
                institution=name,
                institution_id="00000",
                dob=date(1000, 10, 10),
                contact_number="123456789",
                bio="captian",
                profile_image="no profile",
                volunteer_credits=0,
                location="0.0,0.0",
                approve=True
            )
            if self.session.query(UserModelDB).filter(UserModelDB.email == email).first() is None:
                self.session.add(captian)
        self.session.commit()

    def get_unassigned_volunteers(self):
        stmt = select(UserModelDB).join(ElderRecord, UserModelDB.email == ElderRecord.volunteer_email, isouter=True).filter(
            UserModelDB.user_type == "volunteer",
            (ElderRecord.volunteer_email == None) |
            (ElderRecord.status != "assigned")
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
            status=ElderStatus.not_assigned,
            volunteer_email=None,
            service_id=None,
            data=None,
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
            location=user.location,
            institution=user.institution,
            institution_id=user.institution_id,
            approve=user.approve
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
            volunteer_credits=user.volunteer_credits,
            institution=user.institution,
            institution_id=user.institution_id,
            approve=user.approve
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
            timestamp=response["timestamp"],
            reciever=response["reciever"],
            status=response["status"]
        )
        self.session.add(message)
        self.session.commit()
