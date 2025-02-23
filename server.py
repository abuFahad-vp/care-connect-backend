from fastapi import FastAPI, Depends, HTTPException, Query, status, UploadFile, WebSocket, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated, Tuple, Dict
from datetime import timedelta
from model import *
from fastapi.responses import JSONResponse, FileResponse
from autherize import Autherize
from authenticate import Authent
from db_op import DB
from db_init import ElderRecord, UserModelDB, Feedback
from util import Util
from datetime import datetime, timedelta
import os
import json
import asyncio
import uuid
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
db = DB()
Autherize.db = db

os.makedirs("uploads", exist_ok=True)

connected_clients: Dict[str, WebSocket] = {}
new_volunteer_request_queue = asyncio.Queue()
# new_service_request_queue = asyncio.Queue()
active_services: Dict[str, dict] = {}
lock = asyncio.Lock()

@app.get("/ping")
async def ping():
    return {"message": "pinged"}

@app.post("/signup", response_model=UserBase)
async def register(
    user_data: Annotated[dict, Depends(get_user_data)]
) -> UserBase:
    try:
        profile_image: UploadFile = user_data["profile_image"] 
        profile_image = await Authent.authenticate_file(profile_image, 500 * 1024, ["jpg", "jpeg", "png"])
        user_data["profile_image"] = profile_image
        user_data["volunteer_credits"] = 0
        user_create = UserCreate(**user_data)

        new_user = UserBase(
            user_type=user_create.user_type,
            full_name=user_create.full_name,
            email=user_create.email,
            password=Authent.hash_password(user_create.password),
            dob=user_create.dob,
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
    except IntegrityError as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": "User already exist"}
        )
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
    access_token_expires = timedelta(days=Autherize.ACCESS_TOKEN_EXPIRE_DAY)
    access_token = Autherize.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "data": user}

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
            response = await websocket.receive_json()
            current_time = datetime.now()
            # print("Websocket msg: ", response)
            if response["type"] == "load_aayi":
                    for service_id, service in active_services.items():
                        if (service["status"] == ServiceStatus.PENDING and 
                        current_time < service["timeout_end"] and
                        current_user.email not in service["notified_volunteers"]):

                            request = {
                                "type": "new_service_request",
                                "service_id": service_id,
                                "elder_profile": service["elder_profile"],
                                "service_form": service["service_form"],
                                "timeout": str(service["timeout_end"])
                            }
                            await websocket.send_text(json.dumps(request))
                            service["notified_volunteers"].append(current_user.email)

            if response["type"].startswith("new_volunteer_request"):
                await new_volunteer_request_queue.put(response["type"])

            # if response["type"].startswith("new_service_request"):
            #     await new_service_request_queue.put(f"{response["type"]}:{current_user.email}")

            if response["type"] == "service_message":
                await lock.acquire()
                service_id = response["service_id"]
                if service_id in active_services:
                    service = active_services[service_id]

                    if (service["status"] == ServiceStatus.PENDING and 
                    response["status"] == ServiceStatus.ACCEPTED and
                    current_user.user_type == "volunteer"):
                            service["volunteer_email"] = current_user.email
                            service["status"] = ServiceStatus.ACCEPTED
                            print("HERE", connected_clients)
                            if service["elder_email"] in connected_clients:
                                await connected_clients[service["elder_email"]].send_text(json.dumps(
                                    {
                                        "type": "service_message",
                                        "status": service["status"],
                                        "service_id": service_id,
                                        "message": "request_accepted",
                                        "volunteer_profile": str_userbase(current_user)
                                    }
                                ))

                            await connected_clients[current_user.email].send_text(json.dumps(
                                {
                                    "type": "service_message",
                                    "status": service["status"],
                                    "service_id": service_id,
                                    "message": "elder_request_accepted",
                                    "volunteer_profile": str_userbase(current_user)
                                }
                            ))

                    elif service["status"] == ServiceStatus.ACCEPTED:
                        if current_user.user_type == "volunteer":
                            email_check = service["volunteer_email"]
                            partner_email = service["elder_email"]
                        else:
                            email_check = service["elder_email"]
                            partner_email = service["volunteer_email"]

                        if (response["message"] == "initial_request" or
                        email_check != current_user.email):
                                await connected_clients[current_user.email].send_text(json.dumps(
                                    {
                                        "type": "service_message",
                                        "status": "not_assigned",
                                        "service_id": service_id,
                                        "message": "already_assigned",
                                    }
                                ))

                        if current_user.user_type == "volunteer":
                            partner_email = service["elder_email"]
                        else:
                            partner_email = service["volunteer_email"]
                        service["status"] = response["status"]
                        service["message"] = response["message"]
                        if partner_email in connected_clients:
                            await connected_clients[partner_email].send_text(json.dumps(
                                {
                                    "type": "service_message",
                                    "status": service["status"],
                                    "service_id": service_id,
                                    "message": service["message"]
                                }
                            ))
                else:
                    await websocket.send_text(json.dumps({"type":"service_not_found"}))
                
                lock.release()


    except Exception as e:
        print("ERROR: ", e)
        del connected_clients[current_user.email]

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
        current_user: Annotated[UserBase, Depends(Autherize.dep_get_current_user)]
    ):
    try:
        feedback_form["reporter_email"] = current_user.email
        feedback_db = Feedback(**feedback_form)
        db.session.add(feedback_db)
        db.session.commit()
        if "admin@admin.com" in connected_clients:
            await connected_clients["admin@admin.com"].send_text(json.dumps({
                "type": "new_feedback"
            }))
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

@app.get("/user/me/type", response_model=UserBase)
async def read_users_me(current_user: Annotated[UserBase, Depends(Autherize.dep_get_current_user)]):
    return {"type": current_user.user_type}

@app.post("/user/unassign")
async def unassign(request: Annotated[Tuple[UserBase, UserBase, ElderRecord], Depends(Autherize.dep_elder_volunteer_linked)]):
    _, _, record = request

    response = {
        "type": "volunteer_service_message",
        "message": "unassign"
    }

    if record.volunteer_email in connected_clients:
        # print("volunteer present")
        await connected_clients[record.volunteer_email].send_text(json.dumps(response))

    if record.user_email in connected_clients:
        # print("elder present")
        await connected_clients[record.user_email].send_text(json.dumps(response))

    record.volunteer_email = None
    record.status = ElderStatus.not_assigned
    db.session.commit()

    return {"message": "unassigned"}

# elder endpoints
@app.post("/elder/new_volunteer_request")
async def new_volunteer_request(current_user: Annotated[UserBase, Depends(Autherize.dep_only_elder)]):
    record = db.get_elder_record_by_email(current_user.email, current_user.user_type)
    if record.status == ElderStatus.assigned:
        return {"message": "already_assigned"}
    if record.status == ElderStatus.searching_a_volunteer:
        return {"message": "already_searching"}
    if record.status == ElderStatus.not_assigned:
        record.status = ElderStatus.searching_a_volunteer
        db.session.commit()
        return {"message": ElderStatus.searching_a_volunteer}
    return {"message": "updated"}

async def monitor_service(service_id: str):
    while True:
        service = active_services.get(service_id)
        if service is None:
            break

        if service["status"] != "accepted":
            del active_services[service_id]
            print("Service with service id:", service_id, "deleted.")
            for filename in os.listdir("uploads"):
                    if filename.startswith(service_id) and os.path.isfile(f"uploads/{filename}"):
                        os.remove(f"uploads/{filename}")
                        break
        await asyncio.sleep(1)

@app.post("/elder/new_service_request/{timeout_end}")
async def new_service_request(
    timeout_end: datetime,
    service_form: Annotated[ServiceRequestForm, Depends(ServiceRequestForm)],
    current_user: Annotated[UserBase, Depends(Autherize.dep_only_elder)],
    ):

    service_id = str(uuid.uuid4())
    try:
        service_form.check_valid_time()
        service_form.validate_locations()

        service_form_text = {
            "service_id": service_id,
            "description": service_form.description,
            "has_documents": service_form.has_documents,
            "locations": service_form.locations,
            "time_period_from": str(service_form.time_period_from),
            "time_period_to": str(service_form.time_period_to),
            "contact_number": service_form.contact_number,
        }

        if service_form.documents is not None and len(service_form.documents) > 0 and service_form.has_documents:
            file_names = []
            for file in service_form.documents:
                file_names.append(file.filename)
                file_bytes = await file.read()
                with open(f"uploads/{service_id}_{file.filename}", "wb") as buffer:
                    buffer.write(file_bytes)
            service_form_text["documents"] = file_names

        active_services[service_id] = {
            "elder_email": current_user.email,
            "status": ServiceStatus.PENDING,
            "created_at": datetime.now(),
            "service_form": service_form_text,
            "notified_volunteers": [],
            "timeout_end": timeout_end,
            "elder_profile": str_userbase(current_user)
        }

        volunteers = db.session.query(UserModelDB).filter(
            UserModelDB.user_type == "volunteer"
        ).all()

        request = {
            "type": "new_service_request",
            "service_id": service_id,
            "elder_profile": str_userbase(current_user),
            "service_form": service_form_text,
            "timeout": str(timeout_end),
        }

        for volunteer in volunteers:
            if volunteer.email in connected_clients:
                websocket = connected_clients[volunteer.email]
                await websocket.send_text(json.dumps(request))
                active_services[service_id]["notified_volunteers"].append(volunteer.email)
        
        return {"status": "pending", "service_id": service_id}

        # try:
        #     while True:
        #         remaining_time = (timeout_end - datetime.now()).total_seconds()
        #         if remaining_time <= 0:
        #             raise asyncio.TimeoutError

        #         print("Here 1: remaingin time: ", remaining_time)
        #         message: str = await asyncio.wait_for(new_service_request_queue.get(), timeout=remaining_time)
        #         print("Here 2")
        #         message = message.split(":")
                
        #         if message[1] == "accept" and message[2] == current_user.email and message[3] == service_id:
        #             volunteer_profile = db.from_DBModel_to_responseModel(db.get_user_by_email(message[4]))
        #             active_services[service_id]["volunteer_email"] = volunteer_profile.email
        #             active_services[service_id]["status"] = ServiceStatus.ACCEPTED
        #             background_tasks.add_task(monitor_service, service_id)

        #             for email in active_services[service_id]["notified_volunteers"]:
        #                 if email != volunteer_profile.email and email in connected_clients:
        #                     await connected_clients[email].send_text(json.dumps({
        #                         "type": "service_cancelled",
        #                         "service_id": service_id,
        #                         "reason": "accepted_by_another"
        #                     }))

        # except asyncio.TimeoutError:
        #     del active_services[service_id]
        #     return JSONResponse(status_code=408, content={"detail":"Time Out. No volunteer accepted the request", "service_id": service_id})

    except Exception as e:
        db.session.rollback()
        return JSONResponse(status_code=422, content={"detail": str(e), "service_id": service_id})

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

        while True:
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
                Autherize.dep_searching_volunteer(current_user)

                _, volunteer = potential_volunteers.pop(0)

                if volunteer.email in connected_clients:
                    websocket = connected_clients[volunteer.email]

                    try:
                        # Send a request to the volunteer and wait for response
                        request = {
                            "type": "new_volunteer_request",
                            "elder_profile": str_userbase(current_user),
                            "timeout": str(datetime.now() + timedelta(seconds=timeout))
                        }
                        await websocket.send_text(json.dumps(request))
                        message = await asyncio.wait_for(new_volunteer_request_queue.get(), timeout=timeout)
                        new_volunteer_request_queue.task_done()
                        message = message.split(":")
                        if message[1] == "accept" and message[2] == current_user.email:
                            record.volunteer_email = volunteer.email
                            record.status = ElderStatus.assigned
                            db.session.commit()
                            return JSONResponse(
                                status_code=200,
                                content={"detail": "Volunteer assigned successfully"},
                            )
                    except Exception:
                        # Handle connection or other errors
                        # return JSONResponse(
                        #     status_code=422,
                        #     content={"detail": str(e)},
                        # )
                        continue
            # If no volunteer accepts, return a failure response
            # return JSONResponse(
            #     status_code=422,
            #     content={"detail": "No volunteers accepted the request"},
            # )
            # print("IT's running")
            await asyncio.sleep(5)

    except Exception as e:
        db.session.rollback()
        return JSONResponse(status_code=422, content={"detail": str(e)})

@app.get("/elder/record")
async def record(user: Annotated[UserBase, Depends(Autherize.dep_only_elder)]):
    return db.get_elder_record_by_email(user.email, user.user_type)

# volunteer endpoints
@app.post("/volunteer/update_record")
async def update_record(request: Annotated[Tuple[dict, ElderRecord, UserModelDB], Depends(Autherize.dep_update_record)]):
    try:
        record_form, record, volunteer = request
        # record.blood_pressure = record_form["blood_pressure"]
        # record.heart_rate = record_form["heart_rate"]
        # record.blood_sugar = record_form["blood_sugar"]
        # record.oxygen_saturation = record_form["oxygen_saturation"]
        # record.weight = record_form["weight"]
        # record.height = record_form["height"]
        record.data = record_form["data"]
        record.last_check_in = datetime.now()
        volunteer.volunteer_credits += 50
        db.session.commit()
        if record.user_email in connected_clients:
            await connected_clients[record.user_email].send_text(json.dumps({
                "type": "volunteer_service",
                "message": "record_updated"
            }))
        return {"message":"updated"}
    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )

@app.get("/volunteer/get_documents/{service_id}/{document}")
async def update_record(service_id: str, document: str, token: str = Query(...)):

    if not token:
        raise HTTPException(status_code=401, detail="Token missing")

    current_user = Autherize.dep_get_current_user(token)
    current_user = Autherize.dep_only_volunteer(current_user)

    try: 
        if service_id not in active_services:
            raise ValueError("Invalid service_id or there's no service running")

        service = active_services[service_id]
        # if service["volunteer_email"] != current_user.email:
        #     raise Exception("access denied")

        # print(service)

        if service["status"] != ServiceStatus.ACCEPTED and service["status"] != ServiceStatus.PENDING:
            raise ValueError("Service is finished")

        filename = f"{service_id}_{document}"
        file = f"uploads/{filename}"

        if not os.path.isfile(file):
            raise ValueError("file not found")
        
        return FileResponse(file, status_code=200, media_type="application/octet-stream",filename=filename)
        
        

    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )

# @app.get("/volunteer/get_documents/{service_id}/{document}")
# async def update_record(service_id: str, document: str, current_user: Annotated[UserBase, Depends(Autherize.dep_only_volunteer)]):
#     try: 
#         if service_id not in active_services:
#             raise ValueError("Invalid service_id or there's no service running")

#         service = active_services[service_id]
#         # if service["volunteer_email"] != current_user.email:
#         #     raise Exception("access denied")

#         # print(service)

#         if service["status"] != ServiceStatus.ACCEPTED and service["status"] != ServiceStatus.PENDING:
#             raise ValueError("Service is finished")

#         filename = f"{service_id}_{document}"
#         file = f"uploads/{filename}"

#         if not os.path.isfile(file):
#             raise ValueError("file not found")
        
#         return FileResponse(file, status_code=200, media_type="application/octet-stream",filename=filename)
        
        

#     except Exception as e:
#         db.session.rollback()
#         return JSONResponse(
#             status_code=422,
#             content={"detail": str(e)}
#         )

# admin endpoints
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
async def get_users_feedback(current_user: Annotated[UserBase, Depends(Autherize.dep_only_admin)]):
    try:
        feedbacks = db.session.query(Feedback).all()
        return feedbacks
    except Exception as e:
        db.session.rollback()
        return JSONResponse(
            status_code=422,
            content={"detail": str(e)}
        )

@app.put("/admin/feedback/review/{id}")
async def feedback_reviewed(id: int, current_user: Annotated[UserBase, Depends(Autherize.dep_only_admin)]):
    try:
        feedbacks = db.session.query(Feedback).filter(
            Feedback.id == id
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
