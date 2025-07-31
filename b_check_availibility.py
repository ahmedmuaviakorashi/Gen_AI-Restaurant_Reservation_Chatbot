import sqlite3
import datetime as dt
from typing import Dict, Any, Union
from pydantic_schemas import ReservationState
from langsmith import traceable

DB_PATH = "app\\database\\restaurant.db"

@traceable(name="Check Availability Node")
def check_availability_node(state: Union[Dict[str, Any], ReservationState]) -> Dict[str, Any]:
    if isinstance(state, ReservationState):
        state_model = state
        state_dict = state.model_dump()
    else:
        try:
            state_model = ReservationState(**state)
            state_dict = state
        except Exception as e:
            return {
                "assistant_response": f"Error processing reservation: {str(e)}",
                "error": True
            }

    entities = state_model.entities
    
    res_date = entities.res_date
    res_time = entities.res_time
    
    is_available = False
    alternative_slots = []
    assistant_response = ""
    
    rounded_time = _round_time_to_hour(res_time)
    
    is_available = check_slot_availability(res_date, rounded_time)
    
    if is_available:
        assistant_response = f"Great! {rounded_time} on {res_date} is available. Shall I confirm your reservation?"
    else:
        alternative_slots = _suggest_alternative_slots(res_date, rounded_time)
        
        if alternative_slots:
            slots_str = ", ".join(alternative_slots)
            assistant_response = (
                f"Sorry, {rounded_time} on {res_date} isn't available. "
                f"Here are some alternatives: {slots_str}. Would you like one of these?"
            )
        else:
            assistant_response = (
                f"Sorry, {rounded_time} on {res_date} isn't available and "
                "we couldn't find suitable alternatives. Please try another time."
            )
    
    updated_state = state_model.model_copy(update={
        "is_available": is_available,
        "alternative_slots": alternative_slots,
        "assistant_response": assistant_response,
        "chat_history": [
            *state_model.chat_history,
            {"role": "assistant", "content": assistant_response}
        ]
    })
    
    return updated_state

def _round_time_to_hour(time_str: str) -> str:
    try:
        hh_mm = ":".join(time_str.split(":")[:2])
        time_obj = dt.datetime.strptime(hh_mm, "%H:%M")
        return time_obj.replace(minute=0).strftime("%H:%M")
    except ValueError:
        return time_str 

def check_slot_availability(res_date: str, res_time: str) -> bool:
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
                FROM reservations
                WHERE res_date = ?
                AND res_time = ?
                AND status != 'confirmed'
        """, (res_date, res_time))

        count = cursor.fetchone()[0]
        return count == 0 

    except Exception as e:
        print(f"[check_slot_availability] Error: {e}")
        return False
    finally:
        if conn:
            conn.close()


def _suggest_alternative_slots(res_date: str, res_time: str, num_alternatives: int = 3) -> list:

    try:
        cleaned_time = res_time.split(":")[0] + ":" + res_time.split(":")[1]
        base_time = dt.datetime.strptime(cleaned_time, "%H:%M")
        
        alternatives = []
        for offset in [1, -1, 2, -2, 3, -3]: 
            new_time = (base_time + dt.timedelta(hours=offset)).strftime("%H:%M")
            if check_slot_availability(res_date, new_time):
                alternatives.append(new_time)
                if len(alternatives) >= num_alternatives:
                    break
        return alternatives
    except Exception as e:
        print(f"[_suggest_alternative_slots] Error: {e}")
        return []
    