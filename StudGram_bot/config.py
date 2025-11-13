import os
import sys
from dotenv import load_dotenv

# Настраиваем кодировку для Windows
if sys.platform == "win32":
    os.system('chcp 65001 > nul')
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

load_dotenv()

# Константы
API_BASE_URL = "https://api.studgram.ru/api"

API_TOKEN = os.getenv("API_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_TOKEN = os.getenv("OPENROUTER_TOKEN")

# Временное хранилище (в продакшене заменить на БД)
users_db = {}
pending_registrations = {}
active_chats = {}
moderators_db = {}