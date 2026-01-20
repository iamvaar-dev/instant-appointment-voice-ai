# Instant Appointment Voice AI

[![Demo Video](http://img.youtube.com/vi/hHY2KbVJV7Y/0.jpg)](https://youtu.be/hHY2KbVJV7Y)

## Components

This project leverages the following powerful tools:

- **LiveKit**: Real-time voice and video infrastructure.
- **Deepgram**: Speech-to-Text (STT) for fast and accurate transcription.
- **Beyond Presence**: Character/Avatar visualization.
- **Gemini**: LLM for intelligence and conversation flow.
- **Supabase**: Database management.
- **Cartesia**: Text-to-Speech (TTS) for realistic voice generation.

## Local Setup

### 1. Clone the Repository
```bash
git clone https://github.com/iamvaar-dev/instant-appointment-voice-ai
cd instant-appointment-voice-ai
```

### 2. Environment Variables
Create `.env` files in `frontend/` and `backend/` with the following variables:

**Backend (`backend/.env`):**
```env
LIVEKIT_URL=wss://...
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...
BEY_API_KEY=...
GOOGLE_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
```

**Frontend (`frontend/.env`):**
```env
VITE_LIVEKIT_URL=wss://...
```

### 3. Run Locally
To start the backend (Token Server & Agent) and frontend concurrently:

```bash
./run_all.sh
```
