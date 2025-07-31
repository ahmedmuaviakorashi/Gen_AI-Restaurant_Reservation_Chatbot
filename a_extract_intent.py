# extract_intent
import json
import logging
import os
import sqlite3
import sys
import uuid
from typing import Any, Dict

from dotenv import load_dotenv
from langsmith import traceable
from openai import OpenAI

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


load_dotenv()
groq_api_key = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=groq_api_key,
    base_url="https://api.groq.com/openai/v1"
)

DB_PATH = "app/database/restaurant.db"

logger = logging.getLogger("intent_node")
logger.setLevel(logging.INFO)

def log_to_db(user_input, llm_response=None, missing_fields=None, fallback_triggered=False):
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        log_id = str(uuid.uuid4())
        llm_response = llm_response or "N/A"
        missing_fields = missing_fields or ""
        fallback_triggered = bool(fallback_triggered)

        cursor.execute(
            """
            INSERT INTO interaction_logs (log_id, user_input, llm_response, missing_fields, fallback_triggered)
            VALUES (?, ?, ?, ?, ?)
            """,
            (log_id, user_input, llm_response, missing_fields, fallback_triggered)
        )

        conn.commit()
        print(f"[intent_node] Log inserted: {log_id}")

    except Exception as e:
        print(f"[intent_node] DB Logging Error: {e}")

    finally:
        if conn:
            conn.close()


@traceable(name="Extract Intent Node")
def extract_intent(state: Dict[str, Any]) -> Dict[str, Any]:
    user_input = state.user_input
    chat_history = state.chat_history

    try:
        system_prompt = """
You are a highly intelligent and helpful restaurant reservation assistant.

Your job is to interact with users in a professional, friendly tone and help them make, modify, confirm, or cancel table reservations by collecting all required details step-by-step.

## Behavior Instructions:

1. **Talk Like a Human Assistant:**
   - Always Welcome User when strart responding
   - Respond in warm, polite, conversational language.
   - Guide the user naturally and clearly.

2. **Detect the User’s Intent:**
   - Such as: make_reservation, cancel_reservation, modify_reservation, check_availability

3. **Extract These Entities:**
   - `user_name`
   - `email_id`
   - `num_persons`
   - `res_date` — convert "tomorrow", "next Friday" into proper date format: YYYY-MM-DD
   - `res_time` — convert "evening", "8PM", "after Maghrib" into 24-hour format: HH:00:00 ! if user say 19:10 then make it 19:00 or 20:00 let user know that we have fixed time slots.
   - `reservation_type` — e.g., party, meeting, dinner supper etc

4. **If Any Entity Is Missing:**
   - Ask one question at a time to collect it.
   - Do not ask for multiple fields in a single message.
   - Continue the conversation until ALL REQUIRED ENTITY is collected.
   - If user give all entities in one message then you dont need to repeat question unless you need clarification.
   - Always  ask for reservation_type whether user joining for dinner, brthday party meeting etc.
   

5. **Let Users Update Info Freely:**
   - If they change something (e.g., “Make it 3 guests instead”), update your entity values.
   - Confirm the final details with the user.

6. **Handle Off-topic Gracefully:**
   - If the user says something irrelevant like “tell me a joke,” politely guide them back to the reservation process.

7. **Respond in Natural Language AND Include Structured Output:**

8. ** Handling Intent:**
   - if user making reservation for first time then intent = make_reservation
   - if user is cancelling already reserved reservation then intent = cancel_reservation
   - if user is modifying already reserved reservation then intent = modify_reservation

9. ** Intent responses **
   - for cancel_reservation ask for reservation_id and email_id in entity after success greet user and close chat
   - for modify_reservation ask for reservation_id only,  and ask which entity to change. after success greet user and close chat
   - for make_reservation extract all entities.

10. ** Calling Agent Nodes **:
   - if intent is make_reservation then NEVER proceed to check_availability_node until ALL fields are provided.
   - if intent is modify_reservation then NEVER proceed to modify_reservation_node until ALL required fields are provided. (KEEP RESERVATION_ID as STRING i.e 24 > "24")
   - if intent is cancel_reservation then NEVER proceed to cancel_reservation_node until ALL required fields are provided. (KEEP RESERVATION_ID as STRING i.e 24 > "24")

✅ STRICTLY YOUR RESPONSE SHOULD CONTAIN 2 PARTS:
1. `assistant_response` – What you would say to the user (human-style, friendly)
2. `intent` and `entities` – Structured data for backend use
3. DON'T OUTPUT ANYTHING ELSE
## 🔄 Final Output Format (must be valid JSON):
{
  "assistant_response": "Got it! For how many people should I reserve the table?",
  "intent": "make_reservation", (cancel_reservation, modify_reservation)
  "entities": {
    "user_name": null, !ask for it
    "email_id": null, !ask for it
    "num_persons": 2, !ask for it
    "res_date": "2025-07-25", !ask for it
    "res_time": null, !ask for it
    "reservation_type": null !ask for it
  }
}

SAMPLE for any INTENT (MAKE_RESERVATION, CANCEL_RESERVATION or MODIFY_RESERVATION):

Got it! I see you'd like to cancel reservation ID "2".  

{
  "assistant_response": "Got it! I see you'd like to cancel reservation ID \"2\".",
  "intent": "cancel_reservation",
  "entities": {
    "user_name": null,
    "email_id": "hira.k@example.com",
    "num_persons": null,
    "res_date": null,
    "res_time": null,
    "reservation_type": null, < always ask for reservation type whether dinner, party meeting etc
    "reservation_id": "2" < make it string.
  }
}
"""
        messages = [{"role": "system", "content": system_prompt}]

        for msg in chat_history:
            if "user" in msg:
                messages.append({"role": "user", "content": msg["user"]})
            elif "assistant" in msg:
                messages.append({"role": "assistant", "content": msg["assistant"]})

        messages.append({"role": "user", "content": user_input})

        response = client.chat.completions.create(
            #model="gemma2-9b-it",
            model="meta-llama/llama-4-maverick-17b-128e-instruct",
            messages=messages,
            temperature=0.3,
            max_tokens=300,
            stream=False
        )

        llm_json = response.choices[0].message.content.strip()
        try:
            parsed = json.loads(llm_json)
        except json.JSONDecodeError:
            try:
                start = llm_json.find('{')
                end = llm_json.rfind('}') + 1
                if start != -1 and end != -1:
                    parsed = json.loads(llm_json[start:end])
                else:
                    return {
                        "user_input": user_input,
                        "intent": "make_reservation",
                        "assistant_response": llm_json.strip(),
                        "chat_history": chat_history + [
                            {"user": user_input},
                            {"assistant": llm_json.strip()}
                        ]
                    }
            except Exception:
                parsed = {"assistant_response": llm_json.strip()}

        assistant_response = parsed.get("assistant_response") or llm_json.strip()
        log_to_db(user_input=user_input, llm_response=llm_json)

        return {
            "user_input": user_input,
            "intent": parsed.get("intent", "unknown"),
            "entities": parsed.get("entities", {}), 
            "assistant_response": assistant_response,
            "chat_history": chat_history + [
                {"user": user_input},
                {"assistant": assistant_response}
            ]
        }

    except Exception as e:
        error_msg = f"[intent_node] Error: {str(e)}"
        logger.error(error_msg)
        log_to_db(user_input, llm_response=str(e), fallback_triggered=True)

    return {
        "user_input": user_input,
        "intent": parsed.get("intent", "unknown"),
        "entities": parsed.get("entities", {}),
        "assistant_response": assistant_response,
        "chat_history": chat_history + [
            {"user": user_input},
            {"assistant": assistant_response}
        ]
    }

