from db_init import UserModelDB
from model import UserBase
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class DB:
    def __init__(self):
        self.engine = create_engine('sqlite:///amanah.db', echo=True, connect_args={"check_same_thread": False})
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def get_user_by_email(self, email: str):
        user = self.session.query(UserModelDB).filter(UserModelDB.email == email).first()
        return user

    def from_responseModel_to_dbModel(user: UserBase) -> UserModelDB:
        return UserModelDB(
            user_type=user.user_type,
            full_name=user.full_name,
            email=user.email,
            password=user.password,
            dob=user.dob,
            country_code=user.country_code,
            contact_number=user.contact_number,
            bio=user.bio,
            volunteer_credits=0
        )

    def from_DBModel_to_responseModel(self, user: UserModelDB) -> UserBase:
        return UserBase(
            user_type=user.user_type,
            full_name=user.full_name,
            email=user.email,
            password=user.password,
            dob=user.dob,
            country_code=user.country_code,
            contact_number=user.contact_number,
            bio=user.bio,
        )

    def add_user(self, user: UserBase):
        new_user = DB.from_responseModel_to_dbModel(user)
        self.session.add(new_user)
        self.session.commit()