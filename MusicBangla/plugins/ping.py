import time
from pyrogram import filters
from pyrogram.types import Message

import config
from MusicBangla import app
from MusicBangla.database import stats


@app.on_message(filters.command("ping"))
async def ping_cmd(client, message: Message):
    start = time.time()
    msg = await message.reply_text("🏓 <b>পিং চেক করছি...</b>")
    try:
        await client.send_reaction(chat_id=message.chat.id, message_id=message.id, emoji="⚡")
    except Exception:
        pass
    end = time.time()
    latency = round((end - start) * 1000, 2)
    users, chats = await stats()
    await msg.edit(
        f"╭───❀ ✦ ❀───╮\n"
        f"   ⚡ <b>পিং রিপোর্ট</b>\n"
        f"╰───❀ ✦ ❀───╯\n\n"
        f"🏓 <b>লেটেন্সি:</b> <code>{latency} ms</code>\n"
        f"👥 <b>মোট ইউজার:</b> <code>{users}</code>\n"
        f"💬 <b>মোট গ্রুপ:</b> <code>{chats}</code>\n"
        f"🤖 <b>স্ট্যাটাস:</b> অনলাইন ✅\n\n"
        f"💝 মালিক: @{config.OWNER_USERNAME}"
    )
