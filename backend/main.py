# Already included in agent.py via cli.run_app, but creating a separate main if needed.
# For simplicity, we can just run agent.py. 
# But let's creating a dedicated main.py that imports from agent.py if we want to structure it better.
# Actually, the previous file `agent.py` has the __main__ block, so it is sufficient.
# I'll create a dummy main.py that just imports agent to be safe or delete this step if I realize it.
# Let's just create a run script.

import os
import sys
from livekit.agents import cli
from livekit.agents import WorkerOptions
from agent import entrypoint

if __name__ == "__main__":
    # Ensure env vars are loaded
    from dotenv import load_dotenv
    load_dotenv()  # Load from current directory (backend/.env)
    
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
