import os
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from livekit import api
from dotenv import load_dotenv

load_dotenv()  # Load from current directory (backend/.env)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.get("/")
async def root():
    return {"message": "Token Server is Running. Open http://localhost:5173 to use the Voice Agent."}
@app.get("/getToken")
async def get_token(name: str = "User"):
    # Generate a unique room name for this session
    room_name = f"session-{uuid.uuid4().hex[:12]}"
    
    # Generate a token for the user
    token = api.AccessToken(
        os.getenv("LIVEKIT_API_KEY"),
        os.getenv("LIVEKIT_API_SECRET")
    ).with_identity(name) \
    .with_name(name) \
    .with_grants(api.VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
    ))
    
    return {"token": token.to_jwt(), "room": room_name}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
