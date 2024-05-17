from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from uuid import uuid4

app = FastAPI()

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inmemory database for the assesment
users_db = {}
friends_db = {}
friend_requests_db = {}
conversations_db = {}

class User(BaseModel):
    id: str
    name: str

class FriendRequest(BaseModel):
    id: str
    from_user: str
    to_user: str

class Conversation(BaseModel):
    id: str
    participants: List[str]
    messages: List[str] = []

class Message(BaseModel):
    sender: str
    content: str

# Manage real-time conversations
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

    async def send_to_user(self, user_id: str, message: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)

manager = ConnectionManager()

# API endpoints for user management
@app.post("/users/", response_model=User)
async def create_user(name: str):
    user_id = str(uuid4())
    new_user = User(id=user_id, name=name)
    users_db[user_id] = new_user
    friends_db[user_id] = []
    return new_user

@app.get("/users/", response_model=List[User])
async def get_users():
    return list(users_db.values())

@app.post("/users/{user_id}/friend_requests/", response_model=FriendRequest)
async def send_friend_request(user_id: str, friend_id: str):
    if friend_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    request_id = str(uuid4())
    friend_request = FriendRequest(id=request_id, from_user=user_id, to_user=friend_id)
    friend_requests_db[request_id] = friend_request
    await manager.send_to_user(friend_id, f"Friend request from {users_db[user_id].name}")
    return friend_request

@app.post("/users/{user_id}/friend_requests/{request_id}/accept/")
async def accept_friend_request(user_id: str, request_id: str):
    if request_id not in friend_requests_db:
        raise HTTPException(status_code=404, detail="Friend request not found")
    friend_request = friend_requests_db[request_id]
    if friend_request.to_user != user_id:
        raise HTTPException(status_code=403, detail="Cannot accept this friend request")
    friends_db[friend_request.from_user].append(user_id)
    friends_db[user_id].append(friend_request.from_user)
    del friend_requests_db[request_id]
    await manager.send_to_user(friend_request.from_user, f"Friend request accepted by {users_db[user_id].name}")
    return {"message": "Friend request accepted"}

@app.get("/users/{user_id}/friends/", response_model=List[User])
async def get_friends(user_id: str):
    if user_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    friend_ids = friends_db.get(user_id, [])
    return [users_db[friend_id] for friend_id in friend_ids]

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"Message from {user_id}: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(user_id)

# API endpoints for conversation management
@app.post("/conversations/", response_model=Conversation)
async def create_conversation(user_id: str, friend_id: str):
    if user_id not in users_db or friend_id not in users_db:
        raise HTTPException(status_code=404, detail="User not found")
    conversation_id = str(uuid4())
    conversation = Conversation(id=conversation_id, participants=[user_id, friend_id])
    conversations_db[conversation_id] = conversation
    return conversation

@app.get("/conversations/{conversation_id}/", response_model=Conversation)
async def get_conversation(conversation_id: str):
    if conversation_id not in conversations_db:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversations_db[conversation_id]

@app.websocket("/chat/{conversation_id}/{user_id}")
async def chat(websocket: WebSocket, conversation_id: str, user_id: str):
    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = f"{user_id}: {data}"
            if conversation_id in conversations_db:
                conversation = conversations_db[conversation_id]
                if user_id in conversation.participants:
                    conversation.messages.append(message)
                    for participant in conversation.participants:
                        if participant != user_id:
                            await manager.send_to_user(participant, message)
    except WebSocketDisconnect:
        manager.disconnect(user_id)
