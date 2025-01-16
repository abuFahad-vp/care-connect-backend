from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, WebSocket
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated, List, Tuple
from datetime import timedelta
from model import get_user_data, UserCreate, UserBase, ElderStatus, get_feedback, str_userbase, ServiceRequestForm
from fastapi.responses import JSONResponse
from autherize import Autherize
from authenticate import Authent
from db_op import DB
from db_init import ElderRecord, UserModelDB, Feedback
from util import Util
from datetime import datetime, timedelta
import os
import json
import asyncio
from fastapi.middleware.cors import CORSMiddleware

# location in signup form
app = FastAPI()

new_volunteer_request_queue = asyncio.Queue()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # This allows any origin, including null
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)
db = DB()
Autherize.db = db

os.makedirs("uploads", exist_ok=True)

connected_clients = {}

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

# user endpoints
@app.get("/user/know_your_partner")
async def know_your_partner(request: Annotated[Tuple[UserBase, UserBase, ElderRecord], Depends(Autherize.dep_elder_volunteer_linked)]):
    _, partner, record =  request
    partner = partner.model_dump(exclude={"password"})
    return {
        "partner": partner,
        "record": record
    }

@app.post("/user/feedback")
async def feedback(
        feedback_form: Annotated[dict, Depends(get_feedback)], 
        user_record: Annotated[Tuple[UserBase, UserBase, ElderRecord], Depends(Autherize.dep_elder_volunteer_linked)],
    ):
    try:
        from_user, to_user, _ = user_record
        feedback_form["reporter_email"] = from_user.email
        feedback_form["reported_email"] = to_user.email
        feedback_db = Feedback(**feedback_form)
        db.session.add(feedback_db)
        db.session.commit()
        return {"message": "feedbacked sented"}
    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )

@app.get("/user/me", response_model=UserBase)
async def read_users_me(current_user: Annotated[UserBase, Depends(Autherize.dep_get_current_user)]):
    return current_user


# elder endpoints
@app.post("/elder/new_volunteer_request")
async def new_volunteer_request(current_record: Annotated[ElderRecord, Depends(Autherize.dep_no_service_assigned)]):
    current_record.status = ElderStatus.searching_a_volunteer
    db.session.commit()
    return {"message": "updated"}

@app.post("/elder/new_service_request")
async def new_service_request(
    service_form: Annotated[ServiceRequestForm, Depends(ServiceRequestForm)],
    current_user: Annotated[UserBase, Depends(Autherize.dep_only_elder)]):
    try:
        service_form.check_valid_time()
        service_form.document_validation()
        service_form.validate_locations()
        return {"message": "got it"}
    except Exception as e:
        db.session.rollback()
        return JSONResponse(status_code=422, content={"detail": str(e)})


# this will keep searching until a volunteer is found or timeout
@app.get("/elder/find_assign_volunteer/{timeout}")
async def find_assign_volunteer(
    timeout: float,
    request: Annotated[
        Tuple[UserBase, ElderRecord],
        Depends(Autherize.dep_searching_volunteer),
    ]
):
    try:
        current_user, record = request
        lat1, lon1 = map(float, current_user.location.split(","))

        volunteers = db.get_unassigned_volunteers()

        if not volunteers:
            return JSONResponse(
                status_code=422, content={"detail": "No active volunteers"}
            )

        lat1, lon1 = map(float, current_user.location.split(","))
        potential_volunteers = []

        for volunteer in volunteers:
            lat2, lon2 = map(float, volunteer.location.split(","))
            curr_dist = Util.calculate_distance(lat1, lon1, lat2, lon2)
            potential_volunteers.append((curr_dist, volunteer))

        potential_volunteers = sorted(potential_volunteers, key=lambda x: x[0])
        print("connected clinets = ", connected_clients)

        while potential_volunteers:
            _, volunteer = potential_volunteers.pop(0)

            if volunteer.email in connected_clients:
                websocket = connected_clients[volunteer.email]

                try:
                    # Send a request to the volunteer and wait for response
                    request = {
                        "type": f"new_volunteer_request:{current_user.email}",
                        "user_profile": str_userbase(current_user)
                    }
                    await websocket.send_text(json.dumps(request))
                    message = await asyncio.wait_for(new_volunteer_request_queue.get(), timeout=timeout)
                    new_volunteer_request_queue.task_done()

                    if message.split(":")[1] == "accept":
                        record.volunteer_email = volunteer.email
                        record.status = ElderStatus.assigned
                        db.session.commit()
                        return JSONResponse(
                            status_code=200,
                            content={"detail": "Volunteer assigned successfully"},
                        )
                except Exception as e:
                    # Handle connection or other errors
                    continue

        # If no volunteer accepts, return a failure response
        return JSONResponse(
            status_code=422,
            content={"detail": "No volunteers accepted the request"},
        )

    except Exception as e:
        db.session.rollback()
        return JSONResponse(status_code=422, content={"detail": str(e)})

@app.get("/elder/record")
async def record(user: Annotated[UserBase, Depends(Autherize.dep_only_elder)]):
    return db.get_elder_record_by_email(user.email, user.user_type)

# websocket
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Token missing")
    current_user = Autherize.dep_get_current_user(token)
    await websocket.accept()
    connected_clients[current_user.email] = websocket
    try:
        while True:
            response = await websocket.receive_text()
            if response.startswith("new_volunteer_request"):
                await new_volunteer_request_queue.put(response)
    except Exception:
        del connected_clients[current_user.email]
@app.post("/user/unassign")
async def unassign(request: Annotated[Tuple[UserBase, UserBase, ElderRecord], Depends(Autherize.dep_elder_volunteer_linked)]):
    _, _, record = request
    record.volunteer_email = None
    record.status = ElderStatus.not_assigned
    db.session.commit()
    return {"message": "unassigned"}


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

@app.get("/admin/records")
async def get_users(current_user: Annotated[UserBase, Depends(Autherize.dep_only_admin)]):
    try:
        records = db.session.query(ElderRecord).all()
        return records
    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )

@app.get("/admin/users/{email}")
async def get_users_email(email: str, current_user: Annotated[UserBase, Depends(Autherize.dep_only_admin)]):
    try:
        user = db.get_user_by_email(email)
        if user is not None:
            return user
        else:
            raise HTTPException(status_code=422, detail="User not found")
    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )

@app.get("/admin/users")
async def get_users(current_user: Annotated[UserBase, Depends(Autherize.dep_only_admin)]):
    try:
        users = db.session.query(UserModelDB).all()
        return users
    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )

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

@app.get("/admin/feedback")
async def get_feedback(current_user: Annotated[UserBase, Depends(Autherize.dep_only_admin)]):
    try:
        feedbacks = db.session.query(Feedback).all()
        return feedbacks
    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )

@app.put("/admin/feedback/reviewed/{email}")
async def feedback_reviewed(email: str, current_user: Annotated[UserBase, Depends(Autherize.dep_only_admin)]):
    try:
        feedbacks = db.session.query(Feedback).filter(
            Feedback.reporter_email == email
        ).all()

        if not feedbacks:
            raise HTTPException(status_code=422, detail="No feedback found for this email")

        for feedback in feedbacks:
            feedback.status = "reviewed"
        db.session.commit()
        return {"message": "updated"}
    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
           content={"detail": str(e)}
        )