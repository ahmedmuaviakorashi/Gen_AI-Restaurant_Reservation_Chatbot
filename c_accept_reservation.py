import sqlite3
from typing import Dict, Any, Union
from pydantic_schemas import ReservationState
from langsmith import traceable
import datetime

DB_PATH = "app\\database\\restaurant.db"

@traceable(name="Confirm Reservation Node")
def confirm_reservation_node(state: Union[Dict[str, Any], ReservationState]) -> Dict[str, Any]:
    """
    Creates reservation if doesn't exist, then confirms it.
    Returns updated state with confirmation message and reservation ID.
    """
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
        
        if not entities.reservation_id:
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
            
            updated_entities = entities.model_copy(update={"reservation_id": reservation_id})
            state_model = state_model.model_copy(update={"entities": updated_entities})
        
        cursor.execute("""
            UPDATE reservations 
            SET status = 'confirmed', 
                updated_at = CURRENT_TIMESTAMP 
            WHERE reservation_id = ?
            AND status = 'pending'
            """, (state_model.entities.reservation_id,))
        
        if cursor.rowcount == 0:
            cursor.execute("SELECT status FROM reservations WHERE reservation_id = ?", 
                         (state_model.entities.reservation_id,))
            result = cursor.fetchone()
            status = result[0] if result else "not found"
            
            msg = (f"Reservation {state_model.entities.reservation_id} "
                  f"is already {status}" if result 
                  else "Reservation not found")
            return _error_response(state_model, msg)
        
        conn.commit()
        
        cursor.execute("""
            SELECT user_name, res_date, res_time, num_persons 
            FROM reservations 
            WHERE reservation_id = ?
            """, (state_model.entities.reservation_id,))
        user_name, res_date, res_time, num_persons = cursor.fetchone()
        
        confirmation_msg = (
            f"Reservation confirmed! 🎉\n"
            f"• ID: {state_model.entities.reservation_id}\n"
            f"• Name: {user_name}\n"
            f"• Date: {res_date} at {res_time}\n"
            f"• Party size: {num_persons}\n"
            f"• Type: {entities.reservation_type}\n"
            f"Confirmation sent to: {entities.email_id}"
        )
        
        return _success_response(state_model, confirmation_msg)
        
    except sqlite3.Error as e:
        return _error_response(state_model, f"Database error: {str(e)}")
    finally:
        if conn:
            conn.close()

def _success_response(state_model: ReservationState, message: str) -> Dict[str, Any]:
    """Helper for success responses"""
    return state_model.model_copy(update={
        "assistant_response": message,
        "chat_history": [
            *state_model.chat_history,
            {"role": "user", "content": state_model.user_input},
            {"role": "assistant", "content": message}
        ]
    }).model_dump()

def _error_response(state_model: ReservationState, error_msg: str) -> Dict[str, Any]:
    """Helper for error responses"""
    return state_model.model_copy(update={
        "assistant_response": error_msg,
        "chat_history": [
            *state_model.chat_history,
            {"role": "user", "content": state_model.user_input},
            {"role": "assistant", "content": error_msg}
        ],
        "error": True
    }).model_dump()