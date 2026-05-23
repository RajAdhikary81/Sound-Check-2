import logging
from pyrogram import Client
from pytgcalls import PyTgCalls

import config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pytgcalls").setLevel(logging.WARNING)

LOGGER = logging.getLogger("MusicBangla")

# à¦®à§‚à¦² à¦¬à¦Ÿ
app = Client(
    name="MusicBanglaBot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    in_memory=True,
)

# Assistant userbot (VC join à¦•à¦°à¦¾à¦° à¦œà¦¨à§à¦¯)
assistant = Client(
    name="MusicBanglaAssistant",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    session_string=config.STRING_SESSION,
    in_memory=True,
)

# Voice chat handler
calls = PyTgCalls(assistant)
