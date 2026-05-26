import os
import random
from dotenv import load_dotenv

load_dotenv()

# --- Security: All sensitive values MUST come from env vars, no hardcoded defaults ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "")
STRING_SESSION = os.environ.get("STRING_SESSION", "")
MONGO_DB_URI = os.environ.get("MONGO_DB_URI", "")
LOG_GROUP_ID = int(os.environ.get("LOG_GROUP_ID", "0"))
SUPPORT_GROUP = os.environ.get("SUPPORT_GROUP", "")
SUPPORT_CHANNEL = os.environ.get("SUPPORT_CHANNEL", "")
GITHUB_URL = "https://github.com/RajSukh81/MusicBangla"

START_IMAGES = [
    "https://pic-link-bot.lovable.app/i/telegram-1779340031479-5eab5504.jpg",
    "https://pic-link-bot.lovable.app/i/telegram-1779340095109-3b9afb55.jpg",
]

REACTION_EMOJIS = ["🎵", "🔥", "❤️", "🎶", "✨", "🎧", "💫", "🌟", "🎤", "💝", "🥰", "👍"]

PLAY_STICKERS = [
    "CAACAgUAAxkBAAEBVVll0kKAGmTCQzeYTV5SU_T7Q8FZuAACAQYAAuxLAVf2Cqgs0Vy9_jQE",
    "CAACAgIAAxkBAAEKzHRk3pZWevuxOmf-VFEXIYzqgETZFAACOA8AAg6oQUiYpbBafrx_HzAE",
]

START_STICKERS = [
    "CAACAgUAAxkBAAEBVVtl0kKr2YGgxXG8H_xY7DSV5MWFhwACzgkAAvDTKVZmK_S5MfRtbDQE",
]

def random_image():
    return random.choice(START_IMAGES)

def random_emoji():
    return random.choice(REACTION_EMOJIS)

def random_play_sticker():
    return random.choice(PLAY_STICKERS)

def random_start_sticker():
    return random.choice(START_STICKERS)
