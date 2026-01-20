import logging
from livekit.agents import llm
from typing import Annotated # Keep if needed, or remove. I'll keep it just in case but I removed usages.
from db import (
    get_user_by_contact, 
    get_user_by_email,
    get_user_by_contact_or_email,
    create_user, 
    get_appointments, 
    create_appointment,
    reschedule_appointment,
    cancel_appointment, 
    check_availability,
    get_chat_history,
    update_session_user
)

logger = logging.getLogger("voice-agent")

class AgentTools:
    def __init__(self, room, chat_ctx, session_id: str):
        self._user = None
        self._room = room
        self._chat_ctx = chat_ctx
        self._session_id = session_id  # Store session ID

    async def _emit_event(self, event_type: str, message: str):
        if self._room:
            logger.info(f"Emitting event: {event_type} - {message}")
            await self._room.local_participant.publish_data(
                payload=f'{{"type": "{event_type}", "message": "{message}"}}',
                reliable=True
            )

    @llm.function_tool(description="Identify the user by their contact number or email address")
    async def identify_user(
        self, 
        identifier: str
    ):
        """
        Identify the user by their contact number or email address.
        This function searches for an existing user but does NOT create a new user.
        This DOES NOT load chat history - each session is independent.
        
        Args:
            identifier: User's mobile number or email address
        """
        await self._emit_event("tool_call", f"Identifying user: {identifier}")
        logger.info(f"Identifying user with identifier: {identifier}")
        
        # Search by contact number OR email
        user = await get_user_by_contact_or_email(identifier)
        
        if not user:
            await self._emit_event("tool_result", "User not found in system")
            return f"No user found with identifier {identifier}. The user needs to create an account first."
            
        self._user = user
        
        # Update session with user_id (tag this session to this user)
        await update_session_user(self._session_id, user['id'])
        logger.info(f"Session {self._session_id} tagged to user {user['id']}")
        
        # Set user ID in chat context for message saving
        if self._chat_ctx and hasattr(self._chat_ctx, 'set_user_id'):
            self._chat_ctx.set_user_id(user['id'])
        
        msg = f"User identified: {user.get('name', 'Guest')} (ID: {user['id']})."
        
        # NO CHAT HISTORY LOADING - Each session is independent
        logger.info(f"User identified - session-scoped memory only, no history loaded")
        
        await self._emit_event("tool_result", msg)
        return msg

    @llm.function_tool(description="Format a mobile number for verbal confirmation")
    async def verify_mobile_number(
        self,
        mobile_number: str
    ):
        """
        Returns the mobile number formatted for the agent to repeat back to the user.
        Use this to confirm the mobile number before proceeding.
        
        Args:
            mobile_number: The mobile number to format for verification
        """
        # Format the number with spaces for easier verbal confirmation
        # Example: "555-123-4567" or "+1 555 123 4567"
        formatted = mobile_number.replace("-", " ").replace("(", "").replace(")", "")
        return f"I heard your mobile number as: {formatted}. Is that correct?"

    @llm.function_tool(description="Spell out a name letter by letter for verification")
    async def verify_name_spelling(
        self,
        name: str
    ):
        """
        Returns the name spelled out letter by letter for the agent to confirm with the user.
        
        Args:
            name: The name to spell out
        """
        # Spell out each letter with spaces
        spelled = " - ".join(list(name.upper()))
        return f"Let me confirm the spelling: {spelled}. Is that correct?"

    @llm.function_tool(description="Spell out an email address for verification")
    async def verify_email_spelling(
        self,
        email: str
    ):
        """
        Returns the email address spelled out carefully for the agent to confirm with the user.
        
        Args:
            email: The email address to spell out
        """
        # Split email into username and domain for clearer verbal confirmation
        if "@" in email:
            username, domain = email.split("@", 1)
            return f"Let me confirm your email: {username} at {domain}. That's {' '.join(list(username))} AT {' '.join(list(domain))}. Is that correct?"
        else:
            return f"The email format seems incorrect. Please provide it again with the @ symbol."

    @llm.function_tool(description="Create a new user account after collecting all required information")
    async def create_user_account(
        self,
        contact_number: str,
        first_name: str,
        last_name: str,
        email: str
    ):
        """
        Create a new user account with all required information.
        Only call this after:
        1. User has given consent to create an account
        2. All information has been verified (mobile, name, email)
        
        Args:
            contact_number: User's verified mobile number
            first_name: User's verified first name
            last_name: User's verified last name
            email: User's verified email address
        """
        await self._emit_event("tool_call", f"Creating user account for {first_name} {last_name}")
        logger.info(f"Creating new user account: {contact_number}, {first_name} {last_name}, {email}")
        
        # Combine first and last name
        full_name = f"{first_name} {last_name}"
        
        # Create the user
        user = await create_user(contact_number=contact_number, name=full_name, email=email)
        
        if user:
            self._user = user
            
            # Set user ID in chat context
            if self._chat_ctx and hasattr(self._chat_ctx, 'set_user_id'):
                self._chat_ctx.set_user_id(user['id'])
            
            await self._emit_event("tool_result", f"Account created successfully for {full_name}")
            return f"Account created successfully! Welcome {full_name}. Your information has been securely saved."
        else:
            await self._emit_event("tool_result", "Failed to create account")
            return "I'm sorry, there was an error creating your account. Please try again."

    @llm.function_tool(description="Check if a specific date and time slot is available")
    async def check_time_slot_availability(
        self,
        date: str,
        time: str
    ):
        """
        Check if a specific time slot is available for booking.
        This only returns availability status without revealing other users' appointment details.
        
        Args:
            date: The date in YYYY-MM-DD format
            time: The time in HH:MM format (24-hour)
        """
        await self._emit_event("tool_call", f"Checking availability for {date} at {time}")
        logger.info(f"Checking availability: {date} {time}")
        
        is_available = await check_availability(date, time)
        
        if is_available:
            return f"Good news! The time slot on {date} at {time} is available."
        else:
            return f"I'm sorry, the time slot on {date} at {time} is already booked. Would you like to try a different time?"

    @llm.function_tool(description="Get available appointment slots")
    async def fetch_slots(self):
        await self._emit_event("tool_call", "Fetching available slots")
        logger.info("Fetching slots")
        return "Available slots: Tomorrow at 10:00 AM, Tomorrow at 2:00 PM, and Friday at 11:00 AM."

    @llm.function_tool(description="Book an appointment")
    async def book_appointment(
        self,
        start_time: str,
        duration: int = 30
    ):
        """
        Book an appointment.
        args:
            start_time: ISO string of the start time (e.g., 2023-10-27T10:00:00)
            duration: Duration in minutes
        """
        if not self._user:
            return "Please identify the user first before booking."
        
        await self._emit_event("tool_call", f"Booking appointment at {start_time}")
        logger.info(f"Booking appointment for {self._user['id']} at {start_time}")
        appt = await create_appointment(self._user['id'], start_time, duration)
        if appt:
            await self._emit_event("tool_result", "Appointment booked successfully")
            return f"Appointment booked successfully for {start_time}."
        return "Failed to book appointment."

    @llm.function_tool(description="Reschedule an existing appointment to a new time")
    async def reschedule_user_appointment(
        self,
        appointment_id: str,
        new_time: str
    ):
        """
        Reschedule an existing appointment to a new date/time.
        This UPDATES the existing appointment, not creates a new one.
        
        Args:
            appointment_id: The ID of the appointment to reschedule
            new_time: ISO string of the new time (e.g., 2023-10-27T14:00:00)
        """
        if not self._user:
            return "Please identify the user first before rescheduling."
        
        await self._emit_event("tool_call", f"Rescheduling appointment {appointment_id} to {new_time}")
        logger.info(f"Rescheduling appointment {appointment_id} to {new_time}")
        
        # Verify the appointment belongs to this user
        user_appointments = await get_appointments(self._user['id'])
        appointment_exists = any(appt['id'] == appointment_id for appt in user_appointments)
        
        if not appointment_exists:
            return "I couldn't find that appointment. Please check your appointments and try again."
        
        # Reschedule the appointment
        result = await reschedule_appointment(appointment_id, new_time)
        
        if result:
            await self._emit_event("tool_result", "Appointment rescheduled successfully")
            return f"Your appointment has been rescheduled to {new_time}."
        else:
            return "I'm sorry, there was an error rescheduling your appointment. Please try again."

    @llm.function_tool(description="Retrieve user's past and upcoming appointments")
    async def retrieve_appointments(self):
        if not self._user:
            return "Please identify the user first."
        
        await self._emit_event("tool_call", "Retrieving appointments")
        appts = await get_appointments(self._user['id'])
        if not appts:
            return "No active appointments found."
        
        # Format list with IDs for easier cancellation
        summary = "\n".join([f"- Appointment on {a['start_time']} - {a.get('details', 'No details')} (ID: {a['id']})" for a in appts])
        await self._emit_event("tool_result", f"Found {len(appts)} appointments")
        return f"Found {len(appts)} active appointment(s):\n{summary}"

    @llm.function_tool(description="Cancel an appointment by its ID")
    async def cancel_user_appointment(
        self,
        appointment_id: str
    ):
        """
        Cancel a specific appointment by its ID.
        The appointment must belong to the currently identified user.
        
        Args:
            appointment_id: The ID of the appointment to cancel
        """
        if not self._user:
            return "Please identify the user first before canceling an appointment."
        
        await self._emit_event("tool_call", f"Canceling appointment {appointment_id}")
        logger.info(f"Canceling appointment {appointment_id} for user {self._user['id']}")
        
        # First verify the appointment belongs to this user
        user_appointments = await get_appointments(self._user['id'])
        appointment_exists = any(appt['id'] == appointment_id for appt in user_appointments)
        
        if not appointment_exists:
            return f"I couldn't find an active appointment with that ID. Please check your appointments and try again."
        
        # Cancel the appointment
        result = await cancel_appointment(appointment_id)
        
        if result:
            await self._emit_event("tool_result", "Appointment cancelled successfully")
            return "Your appointment has been cancelled successfully. Is there anything else I can help you with?"
        else:
            return "I'm sorry, there was an error cancelling your appointment. Please try again or contact support."
