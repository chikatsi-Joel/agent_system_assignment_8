import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MEMORY_DIR = BASE_DIR / "memory"
LOGS_DIR = BASE_DIR / "logs"
OUTPUTS_DIR = BASE_DIR / "outputs"
DASHBOARD_DIR = BASE_DIR / "dashboard"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-6"

BANKS = ["jpmorgan", "bofa", "citi", "wells_fargo", "goldman"]

MAX_TOKENS = 4096
LOG_FILE = LOGS_DIR / "agent_runs.jsonl"
MEMORY_FILE = MEMORY_DIR / "shared_context.json"
