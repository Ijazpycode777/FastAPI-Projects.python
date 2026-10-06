from fastapi import FastAPI, Depends, HTTPException
import httpx
from .security import get_current_user, hash_password, verify_password, create_access_token 
from sqlalchemy import select
from .engine import SessionLocal, engine
from .models import URL, Base, User
from fastapi.security import  OAuth2PasswordRequestForm
from pydantic import BaseModel, HttpUrl

app = FastAPI()

class Usercreate(BaseModel):
    username: str
    password: str

class URLCheckRequest(BaseModel):
    url: HttpUrl


@app.on_event("startup")
async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
def home():
    return {"message": "Welcome to the URL checker API!"}


@app.post("/register")
async def create_user(user: Usercreate):
    async with SessionLocal() as session:
        new_user = User(username=user.username, hashed_password=hash_password(user.password))
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
        return {"message": "User created successfully", "user_id": new_user.id, "username": new_user.username }

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    async with SessionLocal() as session:
        query = select(User).where(User.username == form_data.username)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        if user is None or not verify_password(form_data.password,
         user.hashed_password):
            raise HTTPException(status_code=400, detail="Invalid username or password")
        access_token = create_access_token(data={"sub": user.username})
        return {"message": "Login successful", "access_token": access_token, "token_type": "bearer"}

@app.post("/urls/check")
async def check_url(data: URLCheckRequest, current_user: User = Depends(get_current_user)):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(str(data.url))
            return {"url": data.url, "status_code": response.status_code, "checked_by": current_user.username }
        except httpx.RequestError as e:
            raise HTTPException(status_code=400, detail=f"Error checking URL: {str(e)}")
