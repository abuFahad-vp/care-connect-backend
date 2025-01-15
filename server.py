from fastapi import FastAPI, Depends, HTTPException, status, UploadFile 
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated, List, Tuple
from datetime import timedelta
from model import get_user_data, UserCreate, UserBase, ElderStatus
from fastapi.responses import JSONResponse
from autherize import Autherize
from authenticate import Authent
from db_op import DB
from db_init import ElderRecord, UserModelDB
from util import Util
import sys
import os

# location in signup form
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
            location=user_create.location,
            bio=user_create.bio,
        )
        db.add_user(new_user)
        if new_user.user_type == "elder":
            db.create_empty_elder_record(new_user)
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
async def new_service_request(current_record: Annotated[ElderRecord, Depends(Autherize.dep_no_service_assigned)]):
    current_record.status = ElderStatus.searching_a_volunteer
    db.session.commit()
    return {"message": "updated"}

@app.get("/find_volunteer")
async def find_volunteer(result: Annotated[Tuple[UserBase, List[UserModelDB]], Depends(Autherize.dep_searching_volunteer)]):
    try:
        current_user, volunteers = result
        lat1, lon1 = current_user.location.split(",")
        lat1, lon1 = (float(lat1), float(lon1))
        min_dist = float(sys.maxsize)
        potential_volunteer = volunteers[0]
        for volunteer in volunteers:
            lat2, lon2 = volunteer.location.split(",")
            lat2, lon2 = (float(lat2), float(lon2))
            curr_dist = Util.calculate_distance(lat1, lon1, lat2, lon2)
            if min_dist > curr_dist:
                potential_volunteer = volunteer
                min_dist = curr_dist
        return {"volunteer": potential_volunteer.email}

    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )