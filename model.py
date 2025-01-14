from typing import Annotated, Literal, List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import date, time
from fastapi import UploadFile, Form, File

class RequestBase(BaseModel):
    description: str = Field(
        ..., 
        min_length=2, 
        max_length=1000, 
        description="Description about the service"
    )
    documents: Optional[List[UploadFile]] = None
    location: str = Field(
        ..., 
        description="Google Maps URL for the location of the elder"
    )
    time_period_from: time = Field(
        ..., 
        description="Task starting time"
    )
    time_period_to: time = Field(
        ..., 
        description="Task ending time"
    )
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

class UserBase(BaseModel):
    """Base model for user data validation"""

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
    bio: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="User's biography",
        examples=["A brief description about the user"]
    )

class UserCreate(UserBase):
    """Model for user creation and validation"""
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

async def get_user_data(
    user_type: Annotated[Literal["volunteer", "elder"], Form()],
    full_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
    dob: Annotated[date, Form()],
    country_code: Annotated[str, Form()],
    contact_number: Annotated[str, Form()],
    bio: Annotated[str, Form()],
    profile_image: Annotated[UploadFile, File()]
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
        "profile_image": profile_image
    }

class User(BaseModel):
    username: str
    email: str | None = None

class UserInDB(User):
    hashed_password: bytes