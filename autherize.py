from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional, Annotated
from datetime import timedelta, datetime, timezone
from jwt.exceptions import InvalidTokenError
import jwt
from fastapi.security import OAuth2PasswordBearer
from db_op import DB
from model import UserBase, ElderStatus, get_record_form
from authenticate import Authent

class Autherize:
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
    SECRET_KEY = "aca9754d810d35c36707c65d81475de59aba95d37c3a133882c5551490490120"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    TIME_GAP = timedelta(seconds=10)
    db: DB = None

    @staticmethod
    def auth_exception(detail):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)

        to_encode.update({"exp": expire})
        encode_jwt = jwt.encode(to_encode, Autherize.SECRET_KEY, algorithm=Autherize.ALGORITHM)
        return encode_jwt

    @staticmethod
    def dep_get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
        credentials_exception = Autherize.auth_exception("invalid credentials")
        try:
            payload = jwt.decode(token, Autherize.SECRET_KEY, algorithms=[Autherize.ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
        except InvalidTokenError:
            raise credentials_exception
        user = Autherize.db.get_user_by_email(username)
        if user is None:
            raise credentials_exception
        return Autherize.db.from_DBModel_to_responseModel(user)

    @staticmethod
    def dep_only_elder(current_user: Annotated[UserBase, Depends(dep_get_current_user)]):
        if current_user.user_type != "elder":
            raise Autherize.auth_exception("not logged in as elder")
        return current_user

    @staticmethod
    def dep_only_volunteer(current_user: Annotated[UserBase, Depends(dep_get_current_user)]):
        if current_user.user_type != "volunteer":
            raise Autherize.auth_exception("not logged in as volunteer")
        return current_user

    @staticmethod
    def dep_no_service_assigned(current_user: Annotated[UserBase, Depends(dep_only_elder)]):
        record = Autherize.db.get_elder_record_by_email(current_user.email, current_user.user_type)
        if record.status != ElderStatus.not_assigned:
            raise Autherize.auth_exception("already assigned or already requested")
        return record

    @staticmethod
    def dep_searching_volunteer(current_user: Annotated[UserBase, Depends(dep_only_elder)]):
        record = Autherize.db.get_elder_record_by_email(current_user.email, current_user.user_type)
        if record.status != ElderStatus.searching_a_volunteer:
            raise Autherize.auth_exception("already assigned or not requested for searching")
        return (current_user, record)
    
    @staticmethod
    def dep_update_record(record_form: Annotated[dict, Depends(get_record_form)], current_user: Annotated[UserBase, Depends(dep_only_volunteer)]):
        record = Autherize.db.get_elder_record_by_email(current_user.email, current_user.user_type)
        volunteer = Autherize.db.get_user_by_email(current_user.email)

        if record is None or record.status != ElderStatus.assigned:
            raise Autherize.auth_exception("access denied")

        if record.last_check_in is not None:
            time_diff = datetime.now() - record.last_check_in
            if time_diff < Autherize.TIME_GAP:
                raise Autherize.auth_exception(f"Time period is not reached. remaining: {Autherize.TIME_GAP - time_diff}")

        return (record_form, record, volunteer)

    @staticmethod
    def dep_elder_volunteer_linked(current_user: Annotated[UserBase, Depends(dep_get_current_user)]):
        record = Autherize.db.get_elder_record_by_email(current_user.email, current_user.user_type)
        if record is None or record.status != ElderStatus.assigned:
            raise Autherize.auth_exception(f"access denied")
        if current_user.user_type == "elder":
            partner = Autherize.db.get_user_by_email(record.volunteer_email)
        else:
            partner = Autherize.db.get_user_by_email(record.user_email)

        return (current_user, Autherize.db.from_DBModel_to_responseModel(partner), record) 
    
    @staticmethod
    def dep_only_admin(current_user: Annotated[UserBase, Depends(dep_get_current_user)]):
        if current_user.email == "admin@admin.com" and Authent.verify_password("admin123", current_user.password):
            return current_user
        raise Autherize.auth_exception("invalid admin credentials")