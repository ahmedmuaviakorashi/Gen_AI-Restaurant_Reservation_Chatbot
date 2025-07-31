import sqlite3
from typing import Dict, Any, Union
from pydantic_schemas import ReservationState
from langsmith import traceable

DB_PATH = "app\\database\\restaurant.db"

@traceable(name="Modify Reservation Node")
def modify_reservation_node(state: Union[Dict[str, Any], ReservationState]) -> Dict[str, Any]:
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

    if getattr(state_model, "intent", "") != "modify_reservation":
        return {
            **state_model.model_dump(),
            "assistant_response": "No modification request detected.",
            "chat_history": [
                *state_model.chat_history,
                {"role": "user", "content": state_model.user_input},
                {"role": "assistant", "content": "No modification request detected."}
            ]
        }

    reservation_id = getattr(entities, "reservation_id", None)
    if not reservation_id:
        msg = "Please provide your reservation ID to modify your booking."
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
            SELECT user_name, email_id, num_persons, reservation_type, res_date, res_time, status
            FROM reservations
            WHERE reservation_id = ?
        """, (str(reservation_id),))  

        reservation = cursor.fetchone()

        if not reservation:
            msg = f"No reservation found with ID {reservation_id}."
            return {
                **state_model.model_dump(),
                "assistant_response": msg,
                "chat_history": [
                    *state_model.chat_history,
                    {"role": "user", "content": state_model.user_input},
                    {"role": "assistant", "content": msg}
                ]
            }

        current_name, current_email, current_persons, current_type, current_date, current_time, current_status = reservation

        updates = []
        values = []

        def add_if_changed(field_name, new_value, current_value):
            if new_value is not None and new_value != current_value:
                updates.append(f"{field_name} = ?")
                values.append(new_value)

        add_if_changed("user_name", getattr(entities, "user_name", None), current_name)
        add_if_changed("email_id", getattr(entities, "email_id", None), current_email)
        add_if_changed("num_persons", getattr(entities, "num_persons", None), current_persons)
        add_if_changed("reservation_type", getattr(entities, "reservation_type", None), current_type)
        add_if_changed("res_date", getattr(entities, "res_date", None), current_date)
        add_if_changed("res_time", getattr(entities, "res_time", None), current_time)

        if not updates:
            msg = "No changes detected. Your reservation remains unchanged."
            return {
                **state_model.model_dump(),
                "assistant_response": msg,
                "chat_history": [
                    *state_model.chat_history,
                    {"role": "user", "content": state_model.user_input},
                    {"role": "assistant", "content": msg}
                ]
            }

        updates.append("updated_at = CURRENT_TIMESTAMP")

        update_query = f"""
            UPDATE reservations
            SET {', '.join(updates)}
            WHERE reservation_id = ?
        """
        values.append(str(reservation_id))  

        cursor.execute(update_query, values)
        conn.commit()

        cursor.execute("""
            SELECT user_name, email_id, num_persons, reservation_type, res_date, res_time, status
            FROM reservations
            WHERE reservation_id = ?
        """, (str(reservation_id),))
        updated = cursor.fetchone()

        response = (
            f"Your reservation (ID: {reservation_id}) has been updated successfully.\n"
            f"Updated details:\n"
            f"- Name: {updated[0]}\n"
            f"- Email: {updated[1]}\n"
            f"- Party Size: {updated[2]}\n"
            f"- Type: {updated[3]}\n"
            f"- Date: {updated[4]}\n"
            f"- Time: {updated[5]}\n"
            f"- Status: {updated[6]}"
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
    finally:
        if conn:
            conn.close()