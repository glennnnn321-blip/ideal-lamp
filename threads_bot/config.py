import os
from dotenv import load_dotenv

load_dotenv()

THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tokyo")

THREADS_API_BASE = "https://graph.threads.net/v1.0"
DB_PATH = os.getenv("DB_PATH", "threads_bot.db")
