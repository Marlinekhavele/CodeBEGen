from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from core.database import get_db
from core.auth import get_password_hash, create_access_token
import uuid
from models.user import User

router = APIRouter()

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

@router.post("/signup")
async def signup(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """User registration endpoint"""
    # Check existing user
    db_user = db.query(User).filter(
        (User.username == user_data.username) |
        (User.email == user_data.email)
    ).first()
    
    if db_user:
        raise HTTPException(
            status_code=400, 
            detail="Username or email already exists"
        )

    # Create new user
    new_user = User(
        id=str(uuid.uuid4()),
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password)
    )
    
    db.add(new_user)
    db.commit()

    # Return token directly after registration
    return {
        "message": "User created successfully",
        "access_token": create_access_token({"sub": new_user.id}),
        "token_type": "bearer"
    }
