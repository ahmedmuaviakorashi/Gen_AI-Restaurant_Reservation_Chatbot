import streamlit as st
from pydantic_schemas import ReservationState
from d_reservation_flow import app

def main():
    st.title("🍽️ Restaurant Reservation Assistant")
    st.write("Book, modify, or cancel your reservation")

    if 'state' not in st.session_state:
        st.session_state.state = ReservationState()
        st.session_state.chat_history = []

    for message in st.session_state.chat_history:
        if message["role"] == "user":
            st.chat_message("user").markdown(message["content"])
        else:
            st.chat_message("assistant").markdown(message["content"])

    user_input = st.chat_input("Type your message here...")

    if user_input:
        if user_input.strip().lower() in ("exit", "quit"):
            st.success("👋 Goodbye!")
            st.stop()

        st.session_state.state.user_input = user_input
        st.session_state.state.turn_count += 1

        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.chat_message("user").markdown(user_input)

        try:
            state_dict = app.invoke(st.session_state.state.model_dump())
            st.session_state.state = ReservationState(**state_dict)

            if st.session_state.state.assistant_response:
                st.session_state.chat_history.append({
                    "role": "assistant", 
                    "content": st.session_state.state.assistant_response
                })
                st.chat_message("assistant").markdown(st.session_state.state.assistant_response)

            if st.session_state.state.intent in ("cancel_reservation", "modify_reservation", "make_reservation"):
                if any(phrase in (st.session_state.state.assistant_response or "").lower() 
                       for phrase in ["confirmed", "cancelled", "modified", "completed"]):
                    st.success("✅ Process complete!")
                    st.balloons()
                    st.session_state.state = ReservationState()  

        except Exception as e:
            error_msg = f"System error: {str(e)}"
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": error_msg
            })
            st.chat_message("assistant").error(error_msg)

if __name__ == "__main__":
    main()