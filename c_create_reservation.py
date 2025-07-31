# app/agent/node/d_create_reservation.py
import sqlite3
from typing import Dict, Any, Union
from pydantic_schemas import ReservationState
from langsmith import traceable
import datetime

DB_PATH = "app\\database\\restaurant.db"

@traceable(name="Create Reservation Node")
def create_reservation_node(state: Union[Dict[str, Any], ReservationState]) -> Dict[str, Any]:
    """
    Creates a new reservation in database with 'pending' status.
    Returns state with reservation_id and confirmation prompt.
    """
    # Input validation
    if isinstance(state, ReservationState):
        state_model = state
    else:
        try:
            state_model = ReservationState(**state)
        except Exception as e:
            return {
                "assistant_response": f"Error processing reservation: {str(e)}",
                "error": True
            }

    entities = state_model.entities
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Insert new reservation
        cursor.execute("""
            INSERT INTO reservations (
                user_name, email_id, num_persons, 
                res_date, res_time, reservation_type,
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entities.user_name,
                entities.email_id,
                entities.num_persons,
                entities.res_date,
                entities.res_time,
                entities.reservation_type,
                'pending',
                datetime.datetime.now().isoformat()
            ))
        
        reservation_id = str(cursor.lastrowid)
        conn.commit()
        
        # Update state with new reservation ID
        updated_entities = entities.model_copy(update={
            "reservation_id": reservation_id,
            "status": "pending"
        })
        
        return {
            **state_model.model_dump(),
            "entities": updated_entities.model_dump(),
            "assistant_response": "Your reservation has been created. Ready to confirm?",
            "chat_history": [
                *state_model.chat_history,
                {"role": "assistant", "content": "Your reservation has been created. Ready to confirm?"}
            ]
        }
        
    except sqlite3.Error as e:
        return {
            **state_model.model_dump(),
            "assistant_response": f"Failed to create reservation: {str(e)}",
            "error": True
        }
    finally:
        if conn:
            conn.close()