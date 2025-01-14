from fastapi import FastAPI, Depends, HTTPException, status, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from datetime import timedelta
from model import get_user_data, UserCreate, UserBase, RequestBase
from fastapi.responses import JSONResponse
from autherize import Autherize
from authenticate import Authent
from db_op import DB
import os

app = FastAPI()
db = DB()
Autherize.db = db

os.makedirs("uploads", exist_ok=True)

@app.post("/signup", response_model=UserBase)
async def register(
    user_data: Annotated[dict, Depends(get_user_data)]
) -> UserBase:
    try:
        profile_image: UploadFile = user_data["profile_image"] 
        file_name = f"profile_image_{user_data["user_type"]}_{user_data["email"]}"
        await Authent.authenticate_and_write_file(profile_image, 500 * 1024, file_name, ["jpg", "jpeg", "png"])
        user_data["profile_image"] = file_name

        user_create = UserCreate(**user_data)

        new_user = UserBase(
            user_type=user_create.user_type,
            full_name=user_create.full_name,
            email=user_create.email,
            password=Authent.hash_password(user_create.password),
            dob=user_create.dob,
            country_code=user_create.country_code,
            contact_number=user_create.contact_number,
            bio=user_create.bio,
        )
        db.add_user(new_user)
        return new_user

    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )


@app.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = Authent.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=Autherize.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = Autherize.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# need to remove: validation checking
@app.get("/users/me/", response_model=UserBase)
async def read_users_me(current_user: Annotated[UserBase, Depends(Autherize.dep_get_current_user)]):
    return current_user

# need to remove: elder type checking
@app.get("/elder_only", response_model=UserBase)
async def elder_only(current_user: Annotated[UserBase, Depends(Autherize.dep_only_elder)]):
    return current_user

@app.post("/new_serive_request")
async def new_service_request(request_base: Annotated[RequestBase, Depends(RequestBase)], current_user: Annotated[UserBase, Depends(Autherize.dep_only_elder)]):
    try:
        Authent.authenticate_request_form(request_base)
        if request_base.documents is not None:
            for doc in request_base.documents:
                await Authent.authenticate_and_write_file(doc, 1024 * 1024, doc.filename)
        print(request_base)
        return {"working": "fine"}
    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )