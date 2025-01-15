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
from datetime import datetime, timedelta
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
        profile_image = await Authent.authenticate_file(profile_image, 500 * 1024, ["jpg", "jpeg", "png"])
        user_data["profile_image"] = profile_image
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
            profile_image=user_create.profile_image,
            volunteer_credits=user_create.volunteer_credits
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

@app.post("/elder/new_serive_request")
async def new_service_request(current_record: Annotated[ElderRecord, Depends(Autherize.dep_no_service_assigned)]):
    current_record.status = ElderStatus.searching_a_volunteer
    db.session.commit()
    return {"message": "updated"}

@app.post("/user/unassign")
async def unassign(request: Annotated[Tuple[UserBase, ElderRecord], Depends(Autherize.dep_elder_volunteer_linked)]):
    _, record = request
    record.status = ElderStatus.not_assigned
    return {"message": "unassigned"}

@app.get("/elder/find_assign_volunteer")
async def find_assign_volunteer(request: Annotated[Tuple[UserBase, ElderRecord, List[UserModelDB]], Depends(Autherize.dep_searching_volunteer)]):
    try:
        current_user, record, volunteers = request
        if len(volunteers) == 0:
            return JSONResponse(
                status_code=422,
                content={"detail": "No active volunteers"}
            )
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

        record.volunteer_email = potential_volunteer.email
        record.status = ElderStatus.assigned
        db.session.commit()

        return {"volunteer": potential_volunteer.email}

    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )

@app.get("/elder/record")
async def record(user: Annotated[UserBase, Depends(Autherize.dep_only_elder)]):
    return db.get_elder_record_by_email(user.email, user.user_type)

@app.get("/user/know_your_partner")
async def know_your_partner(request: Annotated[Tuple[UserBase, ElderRecord], Depends(Autherize.dep_elder_volunteer_linked)]):
    partner, record =  request
    partner = partner.model_dump(exclude={"password"})
    return {
        "partner": partner,
        "record": record
    }

@app.post("/volunteer/update_record")
async def update_record(request: Annotated[Tuple[dict, ElderRecord, UserModelDB], Depends(Autherize.dep_update_record)]):
    try:
        record_form, record, volunteer = request
        record.blood_pressure = record_form["blood_pressure"]
        record.heart_rate = record_form["heart_rate"]
        record.blood_sugar = record_form["blood_sugar"]
        record.oxygen_saturation = record_form["oxygen_saturation"]
        record.weight = record_form["weight"]
        record.height = record_form["height"]
        record.last_check_in = datetime.now()
        volunteer.volunteer_credits += 50
        db.session.commit()
        return {"message":"updated"}
    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )

@app.get("/user/me", response_model=UserBase)
async def read_users_me(current_user: Annotated[UserBase, Depends(Autherize.dep_get_current_user)]):
    return current_user

@app.delete("/admin/delete/{email}")
async def delete_user(email: str, current_user: Annotated[UserBase, Depends(Autherize.dep_only_admin)]):
    try:
        user = db.get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.email == "admin@admin.com":
            raise HTTPException(status_code=404, detail="do you hate your life")
        record = db.get_elder_record_by_email(user.email, user.user_type)
        if record is not None:
            if user.user_type == "elder":
                db.session.delete(record)
            else:
                record.status = ElderStatus.not_assigned
                record.volunteer_email = None
        db.session.delete(user)
        db.session.commit()
        return {"message": f"User with email {email} deleted successfully"}
    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )