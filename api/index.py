import sys
import os

# Add parent directory to sys.path so modules like backend, database, agents, sandbox can be imported cleanly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app

# Vercel entrypoint
handler = app
