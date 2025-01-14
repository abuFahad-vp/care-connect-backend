from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional, Annotated, Literal
from datetime import timedelta, datetime, timezone
from jwt.exceptions import InvalidTokenError
import jwt
from fastapi.security import OAuth2PasswordBearer
from db_op import DB
from model import UserBase, RequestBase

class Autherize:
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
    SECRET_KEY = "aca9754d810d35c36707c65d81475de59aba95d37c3a133882c5551490490120"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
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