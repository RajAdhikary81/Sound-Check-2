import os
import random
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "30137409"))
API_HASH = os.getenv("API_HASH", "3336d0f8c9de7cd33b55c655032fa7b3")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "5358817399"))
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "R4J_81")
STRING_SESSION = os.getenv("STRING_SESSION", "")
MONGO_DB_URI = os.getenv("MONGO_DB_URI", "mongodb+srv://Raj07Sukh:Raj07Sukh@cluster0.1ca9rrn.mongodb.net/?appName=Cluster0")
LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", "-1003935489315"))
SUPPORT_GROUP = os.getenv("SUPPORT_GROUP", "https://t.me/+OvozYu7R1EczMGJl")
SUPPORT_CHANNEL = os.getenv("SUPPORT_CHANNEL", "https://t.me/RupkothaGolpo")
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
