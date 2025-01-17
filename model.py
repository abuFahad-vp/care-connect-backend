from typing import Annotated, Literal, List, Optional, Tuple
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import date, datetime
from fastapi import UploadFile, Form, File, HTTPException
from enum import Enum
import json

class ElderStatus:
    not_assigned: str = "not_assigned"
    searching_a_volunteer: str = "searching_a_volunteer"
    assigned: str = "assigned"

class UserBase(BaseModel):
    user_type: Literal["volunteer", "elder"]
    full_name: str = Field( ..., min_length=2, max_length=100, description="User's full name",)
    email: EmailStr = Field( ..., description="User's email address",)
    password: str = Field( ..., description="Hashed password")
    dob: date = Field( ..., description="Date of birth in YYYY-MM-DD format", examples=["1990-01-01"])
    country_code: str = Field(
        ..., 
        pattern=r"^\+[0-9]{1,4}$",
        description="Country code with + prefix",
        examples=["+1", "+44", "+91"]
    )
    contact_number: str = Field(
        ..., 
        pattern=r"^[0-9]{6,15}$",
        description="Contact number without country code",
        examples=["1234567890"]
    )
    location: str = Field(
        ...,
        pattern=r"^[-+]?\d{1,3}\.\d+,\s?[-+]?\d{1,3}\.\d+$",
        description="Location coords",
        examples=["10.2323,75.12323"],
    )
    bio: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="User's biography",
        examples=["A brief description about the user"]
    )
    volunteer_credits: int = Field(
        ...,
        description="Credits of volunteers"
    )
    profile_image: str = Field(
        ...,
        min_length=3,
        description="Profile image as Base64 encoded string"
    )

class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=8,
        description="Password must be at least 8 characters long",
        examples=["StrongP@ssw0rd"]
    )
    confirm_password: str = Field(
        ...,
        min_length=8,
        description="Must match the new password",
        examples=["StrongP@ssw0rd"]
    )

    @field_validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values.data and v != values.data['password']:
            raise ValueError('Passwords do not match')
        return v

class ServiceRequestForm(BaseModel):
    description: str = Field(..., description="Description about the service required")
    documents: Optional[List[UploadFile]] = Field(
        default=None,
        description="documents attached if any")
    has_documents: bool = Field(..., description="Is there any documents attached")
    locations: List[str] = Field(
        ...,
        description="Locations and Location descriptions"
    )
    time_period_from: datetime = Field(..., description="start time for the service")
    time_period_to: datetime = Field(..., description="end time for the service")
    country_code: str = Field(
        ..., 
        pattern=r"^\+[0-9]{1,4}$",
        description="Country code with + prefix",
        examples=["+1", "+44", "+91"]
    )
    contact_number: str = Field(
        ..., 
        pattern=r"^[0-9]{6,15}$",
        description="Contact number without country code",
        examples=["1234567890"]
    )

    def validate_locations(self):
        if not self.locations or len(self.locations) < 1:
            raise ValueError("Must specify the locations")
        for location in self.locations:
            if "|" not in location:
                raise ValueError("Each location must be in the format 'URL|Description'")
    
    def check_valid_time(self):
        if self.time_period_to < self.time_period_from:
                raise ValueError('Invalid time period')
    

class ServiceStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    ABORTED = "aborted"

async def get_record_form(
    blood_pressure: Annotated[str, Form()] = None,
    heart_rate: Annotated[str, Form()] = None,
    blood_sugar: Annotated[str, Form()] = None,
    oxygen_saturation: Annotated[str, Form()] = None,
    weight: Annotated[float, Form()] = None,
    height: Annotated[float, Form()] = None
):
    return {
        "blood_pressure": blood_pressure,
        "heart_rate": heart_rate,
        "blood_sugar": blood_sugar,
        "oxygen_saturation": oxygen_saturation,
        "weight": weight,
        "height": height
    }

async def get_user_data(
    user_type: Annotated[Literal["volunteer", "elder"], Form()],
    full_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
    dob: Annotated[date, Form()],
    country_code: Annotated[str, Form()],
    contact_number: Annotated[str, Form()],
    location: Annotated[str, Form()],
    bio: Annotated[str, Form()],
    profile_image: Annotated[UploadFile, File()],
    volunteer_credits: Annotated[int, File()] = 0,
):
    return {
        "user_type": user_type,
        "full_name": full_name,
        "email": email,
        "password": password,
        "confirm_password": confirm_password,
        "dob": dob,
        "country_code": country_code,
        "contact_number": contact_number,
        "bio": bio,
        "location": location,
        "profile_image": profile_image,
        "volunteer_credits": volunteer_credits
    }
def str_userbase(current_user: UserBase):
    return {
        "user_type": str(current_user.user_type),
        "full_name": str(current_user.full_name),
        "email": str(current_user.email),
        "dob": str(current_user.dob),
        "country_code": str(current_user.country_code),
        "contact_number": str(current_user.contact_number),
        "bio": str(current_user.bio),
        "location": str(current_user.location),
        "profile_image": str(current_user.profile_image),
        "volunteer_credits": str(current_user.volunteer_credits)
    }

async def get_feedback(
    feedback: Annotated[str, Form()],
    feedback_type: Annotated[str, Form()],
    status: Annotated[str, Form()] = "not_reviewed"
):
    return {
        "feedback": feedback,
        "status": status,
        "feedback_type": feedback_type
    }