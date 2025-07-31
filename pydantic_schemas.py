from pydantic import BaseModel, Field
from typing import Optional, Literal
from typing import Dict, Any



class Entities(BaseModel):
    user_name: Optional[str] = None
    email_id: Optional[str] = None
    num_persons: Optional[int] = None
    res_date: Optional[str] = None
    res_time: Optional[str] = None
    reservation_type: Optional[str] = None
    status: Optional[Literal["pending", "confirmed", "cancelled"]] = "pending"
    reservation_id: Optional[str] = None

class ReservationState(BaseModel):
    user_input: str = Field(default="", description="Current user input")
    chat_history: list = Field(default=[], description="Conversation history")
    intent: Optional[str] = Field(default=None, description="Detected intent")
    entities: Entities = Field(default_factory=Entities, description="Extracted entities")
    assistant_response: Optional[str] = Field(default=None, description="AI response")
    turn_count: int = Field(default=0, description="Conversation turn count")
    max_turns: int = Field(default=10, description="Maximum allowed turns")
    is_available: Optional[bool] = None 

    def model_dump(self, **kwargs):
        return super().model_dump(**kwargs)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        if "entities" in data and isinstance(data["entities"], dict):
            data["entities"] = Entities(**data["entities"])
        return cls(**data)