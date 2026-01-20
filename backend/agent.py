import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import pytz

from livekit import agents
from livekit.agents import JobContext, WorkerOptions, cli, llm
import asyncio
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import deepgram, cartesia, openai, bey, silero

from tools import AgentTools
import db
from db import create_session, delete_session, get_session

# Load .env from backend directory (same location as this file)
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

logger = logging.getLogger("voice-agent")

# Configure Gemini as OpenAI compatible
os.environ["OPENAI_API_KEY"] = os.environ.get("GOOGLE_API_KEY", "").strip()
os.environ["OPENAI_BASE_URL"] = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Verify all required API keys are present
required_keys = ["DEEPGRAM_API_KEY", "CARTESIA_API_KEY", "BEY_API_KEY", "GOOGLE_API_KEY"]
for key in required_keys:
    val = os.environ.get(key, "").strip()
    if val:
        logger.info(f"{key} loaded: {val[:8]}...")
    else:
        logger.error(f"MISSING: {key}")

bey_key = os.environ.get("BEY_API_KEY", "").strip()

# Function to generate system instructions with current date/time
def get_system_instructions():
    """
    Generate system instructions with current date and time.
    This ensures the LLM has accurate temporal context for scheduling.
    """
    # Get current time in IST timezone
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    
    # Format date and time
    current_date = now.strftime("%Y-%m-%d (%B %d, %Y)")
    current_time = now.strftime("%H:%M IST (India Standard Time, UTC+5:30)")
    day_of_week = now.strftime("%A")
    
    return f"""You are a helpful and professional voice assistant for a medical clinic, specializing in appointment scheduling.

## Current Date and Time
**Today is**: {day_of_week}, {current_date}
**Current Time**: {current_time}

> **Important**: Use this date/time information when users mention relative times like "today", "tomorrow", "next week", etc. This ensures accurate appointment scheduling since you don't have access to real-time data.

## Your Capabilities
You can help users with:
- Scheduling new appointments
- Rescheduling existing appointments
- Canceling appointments
- Checking appointment availability

## Conversation Flow

### 1. GREETING
- Start every conversation with a warm greeting
- Ask how you can assist with scheduling, rescheduling, or cancellation

### 2. USER IDENTIFICATION
You MUST identify the user before proceeding with any appointment-related tasks.

**Step 2a: Collect Mobile Number**
- Ask for the user's mobile number
- Use the verify_mobile_number tool to repeat the number back
- Wait for explicit confirmation (e.g., "yes", "correct", "that's right")
- If incorrect, ask them to provide it again

**Step 2b: Search for User**
- Use identify_user tool with the confirmed mobile number
- If user is found, proceed to their request (booking/rescheduling/canceling)
- If user is NOT found, proceed to Step 3 (Account Creation)

### 3. ACCOUNT CREATION (Only if user not found)

**Step 3a: Request Consent**
- Politely inform the user they need to create an account
- Explicitly mention: "We'll need to create a simple account in our secure database. Your information will be kept private and secure, and we will never sell your data to third parties."
- Ask: "Would you like to proceed with creating an account?"
- If user says NO: Politely end the conversation and thank them
- If user says YES: Proceed to collect information

**Step 3b: Collect First Name**
- Ask for their first name
- Use verify_name_spelling tool to spell it back letter by letter
- Wait for confirmation
- If incorrect, ask them to spell it out for you

**Step 3c: Collect Last Name**
- Ask for their last name
- Use verify_name_spelling tool to spell it back letter by letter
- Wait for confirmation
- If incorrect, ask them to spell it out for you

**Step 3d: Collect Email**
- Ask for their email address
- Ask them to spell it clearly
- Use verify_email_spelling tool to repeat it back character by character
- Wait for confirmation
- If incorrect or invalid format, ask them to provide it again

**Step 3e: Create Account**
- Use create_user_account tool with all verified information
- Confirm successful account creation
- Proceed to their original request

### 4. HANDLE USER REQUEST

**For Booking:**
- Use check_time_slot_availability to check specific dates/times
- Once time is confirmed available, use book_appointment
- Confirm the booking details

**For Rescheduling:**
- Use retrieve_appointments to show their current appointments
- Ask which appointment they want to reschedule (by date/time)
- Ask for the new date/time they prefer
- Use check_time_slot_availability to verify new time is available
- Use reschedule_user_appointment with appointment ID and new time
- This UPDATES the existing appointment, does NOT create a duplicate
- Confirm the rescheduled time

**For Canceling:**
- Use retrieve_appointments to show their active appointments
- Ask which appointment they want to cancel (by date/time, since IDs are not user-friendly)
- Match the user's description to find the appointment ID
- Use cancel_user_appointment with the appointment ID
- Confirm the cancellation

**For Checking Appointments:**
- Use retrieve_appointments to list their appointments
- Only show appointments for the identified user (never other users' data)
- Note: This only shows ACTIVE appointments, not cancelled ones

## Important Rules

1. **Always Verify Information**: Repeat back mobile numbers, spell names and emails letter by letter
2. **Wait for Confirmation**: Never proceed until the user explicitly confirms (yes, correct, that's right, etc.)
3. **Privacy First**: Never reveal other users' appointment details. When checking availability, only say if a slot is available or not.
4. **One Step at a Time**: Don't rush. Collect and verify one piece of information before moving to the next
5. **Be Polite and Patient**: Voice conversations can have misunderstandings. Stay calm and helpful
6. **Security Assurance**: When creating accounts, emphasize data privacy and security
7. **Never Auto-Create Users**: Always ask for explicit consent before creating an account
8. **Active Appointments Only**: When showing appointments, only active (non-cancelled) appointments are displayed

## Conversation Style
- Be warm, professional, and empathetic
- Keep responses concise and clear
- Use natural, conversational language
- Acknowledge the user's needs promptly
"""

class PersistentChatContext(llm.ChatContext):
    def __init__(self):
        super().__init__()
        self.user_id = None

    def add_message(self, *, role: str, content: str, **kwargs):
        msg = super().add_message(role=role, content=content, **kwargs)
        if self.user_id:
            asyncio.create_task(db.save_message(self.user_id, role, content))
        return msg

    def set_user_id(self, user_id: str):
        self.user_id = user_id

    def load_messages(self, messages: list):
        for m in messages:
            super().add_message(role=m['role'], content=m['content'])

async def entrypoint(ctx: JobContext):
    logger.info(f"Job started for room {ctx.room.name}")
    
    # Create session record in database
    session_id = ctx.room.name  # Use room name as session ID
    await create_session(session_id)
    logger.info(f"Created session record for {session_id}")
    
    # Generate system instructions with current date/time
    system_instructions = get_system_instructions()
    
    # Initialize Persistent ChatContext
    initial_ctx = PersistentChatContext()
    initial_ctx.add_message(role="system", content=system_instructions)

    logger.info(f"Connecting to room {ctx.room.name}")
    await ctx.connect(auto_subscribe=agents.AutoSubscribe.AUDIO_ONLY)

    # Wait for the first participant to connect
    participant = None
    if ctx.room.remote_participants:
        participant = list(ctx.room.remote_participants.values())[0]
        logger.info(f"Using existing participant: {participant.identity}")
    else:
        logger.info("Waiting for participant to join...")
        participant = await ctx.wait_for_participant()
        logger.info(f"Participant joined: {participant.identity}")

    # Pass session_id to tools
    tools_instance = AgentTools(room=ctx.room, chat_ctx=initial_ctx, session_id=session_id)
    tools_list = llm.find_function_tools(tools_instance)

    # Create session first (required for avatar initialization)
    session = AgentSession()
    logger.info("Agent session created")
    
    # Set up event handlers to track pipeline
    @session.on("agent_started")
    def on_agent_started():
        logger.info("[PIPELINE] Agent started and ready")
    
    @session.on("agent_stopped")
    def on_agent_stopped():
        logger.info("[PIPELINE] Agent stopped")
    
    @session.on("user_speech_committed")
    def on_user_speech(msg):
        logger.info(f"[PIPELINE] ✓ User speech detected: {msg.text[:100]}...")
    
    @session.on("agent_speech_committed")
    def on_agent_speech(msg):
        logger.info(f"[PIPELINE] ✓ Agent speech generated: {msg.text[:100]}...")
    
    @session.on("agent_speech_interrupted")
    def on_interrupted():
        logger.info("[PIPELINE] Agent speech interrupted by user")
    
    @session.on("function_calls_collected")
    def on_function_calls(calls):
        for call in calls:
            logger.info(f"[PIPELINE] ✓ Tool call: {call.function_info.name}")
    
    @session.on("function_calls_finished")
    def on_function_finished(calls):
        logger.info(f"[PIPELINE] ✓ Tool calls completed: {len(calls)}")
    
    # Create the Agent configuration with Silero VAD
    logger.info("Configuring agent with Deepgram STT, Gemini LLM, Cartesia TTS, and Silero VAD")
    
    # Broadcast system initialization status to frontend
    async def broadcast_status(component: str, status: str):
        logger.info(f"Broadcasting status: {component} -> {status}")
        try:
            await ctx.room.local_participant.publish_data(
                payload=f'{{"type": "system_status", "component": "{component}", "status": "{status}"}}',
                reliable=True
            )
            logger.info(f"Broadcasted {component} status")
        except Exception as e:
            logger.error(f"Failed to broadcast status for {component}: {e}")
    
    # 1. Initialize STT
    await broadcast_status("stt", "initializing")
    stt_instance = deepgram.STT()
    logger.info(f"[PIPELINE] Deepgram STT initialized: {type(stt_instance).__name__}")
    await broadcast_status("stt", "ready")
    
    # 2. Initialize LLM
    await broadcast_status("llm", "initializing")
    llm_instance = openai.LLM(model="gemini-2.0-flash-exp")
    logger.info(f"[PIPELINE] Gemini LLM initialized: model=gemini-2.0-flash-exp")
    await broadcast_status("llm", "ready")
    
    # 3. Initialize TTS
    await broadcast_status("tts", "initializing")
    tts_instance = cartesia.TTS(
        voice="a167e0f3-df7e-4d52-a9c3-f949145efdab"  # User-specified voice ID
    )
    logger.info(f"[PIPELINE] Cartesia TTS initialized: {type(tts_instance).__name__} (Voice ID: a167e0f3-df7e-4d52-a9c3-f949145efdab)")
    await broadcast_status("tts", "ready")
    
    # 4. Test Database Connection
    await broadcast_status("database", "initializing")
    try:
        # Quick database connectivity test
        session_test = await get_session(session_id)
        logger.info(f"[PIPELINE] Supabase database connected")
        await broadcast_status("database", "ready")
    except Exception as e:
        logger.error(f"[PIPELINE] Database connection failed: {e}")
        await broadcast_status("database", "error")
    
    # 5. Initialize VAD
    vad_instance = silero.VAD.load()
    logger.info(f"[PIPELINE] Silero VAD loaded: {type(vad_instance).__name__}")
    
    agent_config = Agent(
        instructions=system_instructions,
        vad=vad_instance,
        stt=stt_instance,
        llm=llm_instance,
        tts=tts_instance,
        chat_ctx=initial_ctx,
        tools=tools_list,
    )
    logger.info("[PIPELINE] Agent configuration complete")
    
    # Start the agent session FIRST (audio pipeline must be ready)
    logger.info("Starting agent session...")
    await session.start(agent=agent_config, room=ctx.room)
    logger.info("[PIPELINE] ✓ Agent session started - audio pipeline active")
    
    # Wait for session to be fully ready before proceeding
    await asyncio.sleep(1)
    
    # Initialize Avatar Session AFTER agent session is ready
    await broadcast_status("avatar", "initializing")
    avatar = bey.AvatarSession(api_key=bey_key)
    avatar_ready = False
    
    try:
        logger.info("[PIPELINE] Starting Beyond Avatar Session...")
        # Increase timeout and wait for avatar to be ready
        await asyncio.wait_for(avatar.start(session, room=ctx.room), timeout=20.0)
        logger.info("[PIPELINE] ✓ Avatar session started successfully")
        avatar_ready = True
        await broadcast_status("avatar", "ready")
        # Give avatar extra time to fully initialize streaming
        await asyncio.sleep(2)
    except asyncio.TimeoutError:
        logger.warning("[PIPELINE] ⚠ Avatar session startup timed out. Proceeding with voice only.")
        avatar_ready = False
        await broadcast_status("avatar", "unavailable")
    except Exception as e:
        logger.error(f"[PIPELINE] ✗ Avatar failed: {e}", exc_info=True)
        avatar_ready = False
        await broadcast_status("avatar", "error")
    
    # Only send greeting AFTER both session and avatar are fully ready
    if avatar_ready:
        logger.info("[PIPELINE] Avatar ready - waiting additional 1s before greeting...")
        await asyncio.sleep(1)
    
    logger.info("[PIPELINE] Sending greeting...")
    await session.say("Hello! I'm your clinic appointment assistant. How can I help you today? Would you like to schedule, reschedule, or cancel an appointment?", allow_interruptions=True)
    
    logger.info("[PIPELINE] ✓ Agent is now listening for user speech...")
    
    # Keep session alive until room closes
    try:
        # Wait indefinitely - session will stay active
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        logger.info(f"Session ending for room {ctx.room.name}")
    finally:
        # Clean up session when it ends
        await delete_session(session_id)
        logger.info(f"Deleted session record for {session_id}")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
