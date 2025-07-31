from langgraph.graph import StateGraph, END
from a_extract_intent import extract_intent
from b_check_availibility import check_availability_node
from c_accept_reservation import confirm_reservation_node
from c_cancel_reservation import cancel_reservation_node
from c_modify_reservation import modify_reservation_node
from c_create_reservation import create_reservation_node 
from a_track_entities import track_entities
from pydantic_schemas import ReservationState
from langsmith import traceable

@traceable(name="Reservation Flow")
def build_reservation_graph():
    builder = StateGraph(ReservationState)

    builder.add_node("extract_intent", extract_intent)
    builder.add_node("track_entities", track_entities)
    builder.add_node("check_availability", check_availability_node)
    builder.add_node("create_reservation", create_reservation_node)  
    builder.add_node("confirm_reservation", confirm_reservation_node)
    builder.add_node("modify_reservation", modify_reservation_node)
    builder.add_node("cancel_reservation", cancel_reservation_node)

    builder.set_entry_point("extract_intent")
    
    builder.add_edge("extract_intent", "track_entities")
    
    def route_after_tracking(state: ReservationState) -> str:
        """Determine next step after entity tracking"""
        if state.assistant_response and not state.user_input:
            return END
            
        if state.intent == "make_reservation":
            missing_fields = []
            if not state.entities.user_name:
                missing_fields.append("name")
            if not state.entities.email_id:
                missing_fields.append("email")
            if not state.entities.num_persons:
                missing_fields.append("number of people")
            if not state.entities.res_date:
                missing_fields.append("date")
            if not state.entities.res_time:
                missing_fields.append("time")
            
            if not missing_fields:
                return "check_availability"
                
            return END
            
        elif state.intent == "modify_reservation":
            return _route_modification(state)
            
        elif state.intent == "cancel_reservation":
            return _route_cancellation(state)
            
        return END

    def route_after_availability(state: ReservationState) -> str:
        print(f"[ROUTING DEBUG] is_available: {state.is_available}")
        if not state.is_available:
            return END
        if state.entities.reservation_id:
            return "confirm_reservation"
        return "create_reservation"


    builder.add_conditional_edges(
    "check_availability",
    route_after_availability,
    {
        "create_reservation": "create_reservation",
        "confirm_reservation": "confirm_reservation",
        END: END
    }
)
    builder.add_conditional_edges(
        "track_entities",
        route_after_tracking,
        {
            "check_availability": "check_availability",
            "modify_reservation": "modify_reservation",
            "cancel_reservation": "cancel_reservation",
            "extract_intent": "extract_intent",
            END: END
        }
    )
    


    builder.add_edge("create_reservation", "confirm_reservation")
    builder.add_edge("confirm_reservation", END)
    builder.add_edge("modify_reservation", END)
    builder.add_edge("cancel_reservation", END)

    return builder.compile()

def _has_complete_reservation_details(state: ReservationState) -> bool:
    """Check if all required reservation fields are present"""
    required = [
        state.entities.user_name,
        state.entities.email_id,
        state.entities.num_persons,
        state.entities.res_date,
        state.entities.res_time,
        state.entities.reservation_type
    ]
    return all(field is not None for field in required)

def _route_modification(state: ReservationState) -> str:
    """Route modification requests"""
    if not state.entities.reservation_id:
        return "extract_intent"
    if any([state.entities.user_name, state.entities.num_persons, 
            state.entities.res_date, state.entities.res_time]):
        return "modify_reservation"
    return "extract_intent"

def _route_cancellation(state: ReservationState) -> str:
    """Route cancellation requests"""
    if not state.entities.reservation_id or not state.entities.email_id:
        return "extract_intent"
    return "cancel_reservation"

app = build_reservation_graph()