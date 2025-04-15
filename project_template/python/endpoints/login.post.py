from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import timedelta
from core.database import get_db
from sqlalchemy.orm import Session
from core.auth import verify_password, create_access_token
from models.user import User

router = APIRouter()

class UserAuth(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(
    user_data: UserAuth,
    db: Session = Depends(get_db)
):
    """User authentication endpoint"""
    user = db.query(User).filter(User.username == user_data.username).first()
    
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    # Generate token with expiration
    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(hours=1)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username
    }
