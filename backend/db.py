import os
import asyncio
from supabase import create_client, Client
from dotenv import load_dotenv

# Load env from the same directory as this file
load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)

async def get_user_by_contact(contact_number: str):
    response = supabase.table("users").select("*").eq("contact_number", contact_number).execute()
    if response.data:
        return response.data[0]
    return None

async def get_user_by_email(email: str):
    """Get user by email address"""
    response = supabase.table("users").select("*").eq("email", email).execute()
    if response.data:
        return response.data[0]
    return None

async def get_user_by_contact_or_email(identifier: str):
    """
    Get user by either contact number or email.
    Tries contact number first, then email.
    """
    # Try contact number first
    user = await get_user_by_contact(identifier)
    if user:
        return user
    
    # If not found, try email
    user = await get_user_by_email(identifier)
    return user

async def create_user(contact_number: str, name: str = None, email: str = None):
    """Create a new user with contact number, name, and optional email"""
    data = {
        "contact_number": contact_number, 
        "name": name
    }
    if email:
        data["email"] = email
    
    response = supabase.table("users").insert(data).execute()
    if response.data:
        return response.data[0]
    return None


async def get_user_by_id(user_id: str):
    response = supabase.table("users").select("*").eq("id", user_id).execute()
    if response.data:
        return response.data[0]
    return None

async def get_appointments(user_id: str):
    # Get user's contact number first
    user = await get_user_by_id(user_id)
    if not user:
        return []
    
    # Only fetch active (booked) appointments, not cancelled ones
    response = supabase.table("appointments").select("*").eq("contact_number", user["contact_number"]).eq("status", "booked").execute()
    # Format to match expected structure
    appointments = []
    for appt in response.data:
        appointments.append({
            "id": appt["id"],
            "start_time": appt["appointment_time"],
            "status": appt["status"],
            "details": appt.get("details", ""),
            "created_at": appt.get("created_at")
        })
    return appointments

async def create_appointment(user_id: str, start_time: str, duration_mins: int = 30, summary: str = None):
    # Check for conflicts? For now, just insert.
    # Note: The appointments table uses 'contact_number' not 'user_id'
    # First get the user's contact number
    user = await get_user_by_id(user_id)
    if not user:
        return None
    
    # Combine duration and summary into details field
    details_text = summary or f"{duration_mins} minute appointment"
    
    data = {
        "contact_number": user["contact_number"],
        "appointment_time": start_time,
        "details": details_text,
        "status": "booked"
    }
    response = supabase.table("appointments").insert(data).execute()
    if response.data:
        return response.data[0]
    return None

async def reschedule_appointment(appointment_id: str, new_time: str):
    """
    Reschedule an existing appointment by updating its time.
    
    Args:
        appointment_id: The ID of the appointment to reschedule
        new_time: ISO string of the new time (e.g., 2023-10-27T14:00:00)
    """
    data = {
        "appointment_time": new_time
    }
    response = supabase.table("appointments").update(data).eq("id", appointment_id).eq("status", "booked").execute()
    if response.data:
        return response.data[0]
    return None

async def cancel_appointment(appointment_id: str):
    response = supabase.table("appointments").update({"status": "cancelled"}).eq("id", appointment_id).execute()
    return response.data

async def check_availability(date: str, time_slot: str):
    """
    Check if a time slot is available without revealing other users' appointment details.
    Returns a boolean indicating availability.
    
    Args:
        date: Date in YYYY-MM-DD format
        time_slot: Time in HH:MM format
    """
    # Construct the datetime string
    datetime_str = f"{date}T{time_slot}:00"
    
    # Query for any appointments at this exact time
    response = supabase.table("appointments").select("id").eq("appointment_time", datetime_str).eq("status", "booked").execute()
    
    # If no appointments found, slot is available
    is_available = len(response.data) == 0
    return is_available

async def save_message(user_id: str, role: str, content: str):
    data = {
        "user_id": user_id,
        "role": role,
        "content": content
    }
    supabase.table("messages").insert(data).execute()

async def get_chat_history(user_id: str, limit: int = 50):
    response = supabase.table("messages").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
    # Reverse to get chronological order
    return response.data[::-1] if response.data else []

# ============================================================================
# Session Memory Functions
# ============================================================================

async def create_session(session_id: str):
    """
    Create a new session record.
    Called when a new LiveKit session starts.
    Uses upsert to handle cases where session already exists.
    """
    data = {
        "session_id": session_id,
        "user_id": None,  # Not identified yet
        "metadata": {},
        "started_at": "now()",
        "last_activity_at": "now()"
    }
    # Use upsert to avoid duplicate key errors
    response = supabase.table("session_memory").upsert(data, on_conflict="session_id").execute()
    return response.data[0] if response.data else None

async def update_session_user(session_id: str, user_id: str):
    """
    Update session with identified user_id.
    Called when user is successfully identified.
    """
    data = {
        "user_id": user_id,
        "last_activity_at": "now()"
    }
    response = supabase.table("session_memory").update(data).eq("session_id", session_id).execute()
    return response.data[0] if response.data else None

async def get_session(session_id: str):
    """
    Get session information.
    """
    response = supabase.table("session_memory").select("*").eq("session_id", session_id).execute()
    return response.data[0] if response.data else None

async def delete_session(session_id: str):
    """
    Delete session when it ends.
    Called when LiveKit session closes.
    """
    response = supabase.table("session_memory").delete().eq("session_id", session_id).execute()
    return response.data
