import sqlite3
from typing import Dict, Any, Union
from pydantic_schemas import ReservationState
from langsmith import traceable

DB_PATH = "app\\database\\restaurant.db"
DEFAULT_DATE = "2000-01-01"
DEFAULT_TIME = "00:00"

@traceable(name="Cancel Reservation Node")
def cancel_reservation_node(state: Union[Dict[str, Any], ReservationState]) -> Dict[str, Any]:
    """
    Handles reservation cancellation with proper state validation.
    Accepts both dict and ReservationState inputs.
    """
    if isinstance(state, ReservationState):
        state_model = state
    else:
        try:
            state_model = ReservationState(**state)
        except Exception as e:
            return {
                "assistant_response": f"Error processing reservation: {str(e)}",
                "error": True,
                "chat_history": state.get("chat_history", []) if isinstance(state, dict) else []
            }

    entities = state_model.entities

    if state_model.intent != "cancel_reservation":
        return {
            "assistant_response": "No cancellation request detected.",
            "chat_history": state_model.chat_history,
            "error": True
        }

    reservation_id = getattr(entities, "reservation_id", None)
    email_id = getattr(entities, "email_id", None)

    if not reservation_id:
        msg = "Please provide your reservation ID to cancel your booking."
    elif not email_id:
        msg = "Please provide the email used for the reservation."
    else:
        msg = None

    if msg:
        return {
            **state_model.model_dump(),
            "assistant_response": msg,
            "chat_history": [
                *state_model.chat_history,
                {"role": "user", "content": state_model.user_input},
                {"role": "assistant", "content": msg}
            ]
        }

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_name, res_date, res_time, status, email_id 
            FROM reservations 
            WHERE reservation_id = ?
        """, (str(reservation_id),)) 

        row = cursor.fetchone()

        if not row:
            response = f"No reservation found with ID {reservation_id}."
        else:
            user_name, res_date, res_time, status, db_email = row

            if db_email.lower() != email_id.lower():
                response = "The provided email does not match our records."
            elif status == "cancelled":
                response = f"Reservation ID {reservation_id} is already cancelled."
            else:
                cursor.execute("""
                    UPDATE reservations 
                    SET status = 'cancelled',
                        res_date = ?,
                        res_time = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE reservation_id = ? AND email_id = ?
                """, (DEFAULT_DATE, DEFAULT_TIME, str(reservation_id), email_id))
                conn.commit()

                response = (
                    f"Reservation ID {reservation_id} for {user_name} has been cancelled.\n"
                    f"Thank you for using our services."
                )

        return {
            **state_model.model_dump(),
            "assistant_response": response,
            "chat_history": [
                *state_model.chat_history,
                {"role": "user", "content": state_model.user_input},
                {"role": "assistant", "content": response}
            ]
        }

    except sqlite3.Error as e:
        error_msg = f"Database error: {str(e)}"
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
    finally:
        if conn:
            conn.close()

    return {
        **state_model.model_dump(),
        "assistant_response": error_msg,
        "chat_history": [
            *state_model.chat_history,
            {"role": "user", "content": state_model.user_input},
            {"role": "assistant", "content": error_msg}
        ],
        "error": True
    }