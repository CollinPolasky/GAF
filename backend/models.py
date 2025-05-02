from pydantic import BaseModel
from typing import List, Optional

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    tools: Optional[List[str]] = None
    conversation_id: Optional[str] = "default" 