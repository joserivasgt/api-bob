from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict

app = FastAPI()

# Models
class User(BaseModel):
    id: int
    name: str

class Message(BaseModel):
    sender_id: int
    content: str

class Conversation(BaseModel):
    id: int
    participants: List[int]
    messages: List[Message] = []

# In-memory storage
users: Dict[int, User] = {}
conversations: Dict[int, Conversation] = {}

# User Endpoints
@app.post("/users/", response_model=User)
def create_user(user: User):
    if user.id in users:
        raise HTTPException(status_code=400, detail="User already exists")
    users[user.id] = user
    return user

@app.get("/users/{user_id}", response_model=User)
def get_user(user_id: int):
    user = users.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.get("/users/", response_model=List[User])
def list_users():
    return list(users.values())

# Conversation Endpoints
@app.post("/conversations/", response_model=Conversation)
def create_conversation(conversation: Conversation):
    if conversation.id in conversations:
        raise HTTPException(status_code=400, detail="Conversation already exists")
    conversations[conversation.id] = conversation
    return conversation

@app.get("/conversations/{conversation_id}", response_model=Conversation)
def get_conversation(conversation_id: int):
    conversation = conversations.get(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@app.post("/conversations/{conversation_id}/messages/", response_model=Message)
def add_message(conversation_id: int, message: Message):
    conversation = conversations.get(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if message.sender_id not in conversation.participants:
        raise HTTPException(status_code=400, detail="Sender not in conversation")
    conversation.messages.append(message)
    return message

@app.get("/conversations/{conversation_id}/messages/", response_model=List[Message])
def list_messages(conversation_id: int):
    conversation = conversations.get(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation.messages
