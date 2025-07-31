from typing import Dict, Any
from pydantic_schemas import ReservationState, Entities
from langsmith import traceable

@traceable(name="Track Entities Node")
def track_entities(state: Dict[str, Any] | ReservationState) -> Dict[str, Any]:
    if isinstance(state, ReservationState):
        state_model = state
    else:
        try:
            state_model = ReservationState(**state)
        except Exception as e:
            return {
                **state,
                "assistant_response": f"Error parsing state: {str(e)}"
            }

    existing_entities = state_model.entities.model_dump()  
    incoming = state if isinstance(state, dict) else state_model.model_dump()  
    raw_new_entities = incoming.get("entities", {})

    if isinstance(raw_new_entities, Entities):
        new_entities = raw_new_entities.model_dump()
    elif isinstance(raw_new_entities, dict):
        new_entities = raw_new_entities
    else:
        new_entities = {}

    merged_entities = {
        key: new_entities.get(key) if new_entities.get(key) is not None else existing_entities.get(key)
        for key in set(existing_entities) | set(new_entities)
    }

    updated_state = state_model.model_copy(update={"entities": Entities(**merged_entities)})
    return updated_state.model_dump()
