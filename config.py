import os
import random
from dotenv import load_dotenv

load_dotenv()

# --- Security: All sensitive values MUST come from env vars, no hardcoded defaults ---
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
OWNER_USERNAME = os.environ.get("OWNER_USERNAME", "R4J_81")
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

# --- Colorful reaction emojis (massively expanded) ---
REACTION_EMOJIS = [
    "🎵", "🔥", "❤️", "🎶", "✨", "🎧", "💫", "🌟", "🎤", "💝",
    "🥰", "👍", "🎉", "💜", "💙", "💚", "🧡", "💛", "🤩", "😍",
    "🫶", "🙌", "⚡", "🌈", "🎸", "🎹", "🎷", "🎺", "🎻", "💃",
    "🕺", "🤟", "👏", "💖", "🦋", "🌸", "🍀", "🎀", "🏆", "💎",
    "❤️‍🔥", "🫰", "💯", "🫡", "🤗", "😎", "🥳", "🫠", "😇",
    "🪩", "🎊", "🌺", "🌻", "🌷", "🌹", "🫧", "💐", "🍭", "🍬",
    "🧸", "🎈", "🎁", "🎠", "🎡", "🎢", "🎪", "🎭", "🎨",
]

# --- Big emoji messages for chat reactions ---
BIG_EMOJI_REACTIONS = [
    "🎵🎶🎧", "🔥🔥🔥", "❤️‍🔥❤️‍🔥", "✨💫⭐", "🎤🎸🎹",
    "💜💙💚", "🎉🥳🎊", "😍🥰🤩", "🙌👏🤟", "💃🕺🪩",
    "🌈🌸🦋", "💎🏆⚡", "🎷🎺🎻", "🫶❤️💝", "💯🔥✨",
    "🎧🎵🎶", "🌟💫🌈", "🥳🎉🎊", "😎🤟🔥", "🫰💖💗",
    "🎸⚡🔥", "🪩💃🕺", "🎹🎼🎵", "💐🌹🌸", "🧸🎀🎁",
    "🎠🎡🎢", "🍭🍬🎈", "🎪🎭🎨", "💝💖💗", "⭐🌟✨",
]

# --- Song playing big emojis ---
PLAY_BIG_EMOJIS = [
    "🎵", "🎶", "🎧", "🎤", "🎸", "🎹", "🎷", "🎺", "🎻", "💿",
    "📀", "🎼", "🎙️", "🔊", "🔉", "🪗", "🥁", "🪘", "🪕", "🎚️",
]

# --- Video playing big emojis ---
VIDEO_BIG_EMOJIS = [
    "🎬", "📹", "🎥", "📽️", "🎞️", "📺", "🖥️", "📡", "🎦", "🎭",
]

# --- Play stickers (music-themed, animated) ---
PLAY_STICKERS = [
    "CAACAgUAAxkBAAEBVVll0kKAGmTCQzeYTV5SU_T7Q8FZuAACAQYAAuxLAVf2Cqgs0Vy9_jQE",
    "CAACAgIAAxkBAAEKzHRk3pZWevuxOmf-VFEXIYzqgETZFAACOA8AAg6oQUiYpbBafrx_HzAE",
    "CAACAgIAAxkBAAENbcZn1K4AAXdFoMv9PJC-8j4nHwwJjgACTAADQbVWDNKBj4oAAbWyPDYE",
    "CAACAgIAAxkBAAENbchn1K5TzqkLh-iq5IRZYV-pL2gxLAACqgADO2AkFCqIJGKVn9MWNQQ",
    "CAACAgIAAxkBAAENbcpn1K6NpPp-cKl0qVuHJSWO73W3KgACFAADwDZPE1x3kw-daxuJNgQ",
    "CAACAgEAAxkBAAENbc5n1K7mE6BjuwqRDNl5wL-7vTm3iQACGQMAApzHIET_1MlIq_2CljYE",
    "CAACAgIAAxkBAAENbdBn1K8kbHxuQcnL3-f7vafIdyHMqAACCwADwDZPE_Ah4kJa5wPFNgQ",
    "CAACAgIAAxkBAAENbdJn1K9H4nJUqIvCc8Yz3VlFyXnLdAACYQADr8ZRGtLIBNmrYBwrNgQ",
]

# --- Start/Welcome stickers ---
START_STICKERS = [
    "CAACAgUAAxkBAAEBVVtl0kKr2YGgxXG8H_xY7DSV5MWFhwACzgkAAvDTKVZmK_S5MfRtbDQE",
    "CAACAgIAAxkBAAENbdRn1K-J_lnqXUEz2F5hE2g3X90mCQACIgEAAladvQoq8bFEP2mDWTYE",
    "CAACAgIAAxkBAAENbdZn1K-0-D98JhZhTDXwm-B3HjLH4QACIwADr8ZRGnT2MWBwWq3aNgQ",
    "CAACAgIAAxkBAAENbdhn1K_fbPh-g9xB39lVxMD3bqD1jwACFQADwDZPE2H11IUYz_7BNgQ",
]

# --- Queue/Skip stickers ---
QUEUE_STICKERS = [
    "CAACAgIAAxkBAAENbdpn1LAl2CxVrHxXPz1eKpH2VBKKuQACMQADr8ZRGmB9tjFFkV70NgQ",
    "CAACAgIAAxkBAAENbdxn1LBQQGQwlq6ZiS8b0MH_5-YFYQACGgADr8ZRGj_MRhkb5fmKNgQ",
]

# --- Stop stickers ---
STOP_STICKERS = [
    "CAACAgIAAxkBAAENbd5n1LCIavBCL_m7R2e5A1AAARN5-pcAAjIAA6_GURoQKu08VW-bSzYE",
]

# --- Fun reaction emojis for different events ---
SEARCH_EMOJIS = ["🔍", "🔎", "🧐", "👀", "🕵️", "🔭", "🎯", "🫣", "🤔", "🧭"]
DOWNLOAD_EMOJIS = ["📥", "⬇️", "💾", "📦", "🚀", "⚡", "🌊", "🏎️", "💨", "🛸"]
SUCCESS_EMOJIS = ["✅", "🎉", "🥳", "🎊", "💯", "🏆", "⭐", "🌟", "🔥", "💪"]
ERROR_EMOJIS = ["❌", "😔", "🥲", "💔", "🫣", "😵", "🤕", "😢", "🫠", "😿"]

def random_image():
    return random.choice(START_IMAGES)

def random_emoji():
    return random.choice(REACTION_EMOJIS)

def random_play_sticker():
    return random.choice(PLAY_STICKERS)

def random_start_sticker():
    return random.choice(START_STICKERS)

def random_queue_sticker():
    return random.choice(QUEUE_STICKERS)

def random_stop_sticker():
    return random.choice(STOP_STICKERS)

def random_search_emoji():
    return random.choice(SEARCH_EMOJIS)

def random_download_emoji():
    return random.choice(DOWNLOAD_EMOJIS)

def random_success_emoji():
    return random.choice(SUCCESS_EMOJIS)

def random_error_emoji():
    return random.choice(ERROR_EMOJIS)

def random_big_emoji():
    return random.choice(BIG_EMOJI_REACTIONS)

def random_play_big_emoji():
    return random.choice(PLAY_BIG_EMOJIS)

def random_video_big_emoji():
    return random.choice(VIDEO_BIG_EMOJIS)
