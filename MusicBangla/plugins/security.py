"""
Security & Admin plugin — Owner-only commands:
- /ban <user_id> — ব্যবহারকারী ব্যান
- /unban <user_id> — ব্যান মুক্ত
- /banlist — ব্যান লিস্ট
- /broadcast <message> — সব গ্রুপে মেসেজ
- /block <url_pattern> — URL ব্লক
- /logs — Recent bot logs
"""

import asyncio
import re
import time
from pyrogram import filters
from pyrogram.types import Message

import config
from MusicBangla import app, LOGGER
from MusicBangla.database import db

# Collections
banned_col = db.banned_users
blocked_urls_col = db.blocked_urls

# In-memory cache (refreshed on startup)
BANNED_USERS = set()
BLOCKED_PATTERNS = []
_LOG_BUFFER = []
_MAX_LOG = 50


def log_action(action: str):
    """Store recent security actions"""
    _LOG_BUFFER.append(f"[{time.strftime('%H:%M:%S')}] {action}")
    if len(_LOG_BUFFER) > _MAX_LOG:
        _LOG_BUFFER.pop(0)


async def load_security_data():
    """Load banned users and blocked URLs from DB"""
    global BANNED_USERS, BLOCKED_PATTERNS
    try:
        async for doc in banned_col.find():
            BANNED_USERS.add(doc["_id"])
        async for doc in blocked_urls_col.find():
            BLOCKED_PATTERNS.append(doc["pattern"])
        LOGGER.info(f"Security loaded: {len(BANNED_USERS)} bans, {len(BLOCKED_PATTERNS)} blocked patterns")
    except Exception as e:
        LOGGER.warning(f"Security load error: {e}")


def is_banned(user_id: int) -> bool:
    return user_id in BANNED_USERS


def is_url_blocked(text: str) -> bool:
    for pattern in BLOCKED_PATTERNS:
        try:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        except Exception:
            pass
    return False


# --- Owner-only filter ---
owner_filter = filters.user(config.OWNER_ID) & filters.private


@app.on_message(filters.command("ban") & owner_filter)
async def ban_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("ব্যবহার: <code>/ban user_id</code>")
    try:
        uid = int(message.command[1])
        if uid == config.OWNER_ID:
            return await message.reply_text("নিজেকে ব্যান করা যাবে না!")
        BANNED_USERS.add(uid)
        await banned_col.update_one({"_id": uid}, {"$set": {"_id": uid}}, upsert=True)
        log_action(f"BAN: {uid}")
        await message.reply_text(f"🚫 <code>{uid}</code> ব্যান করা হয়েছে।")
    except ValueError:
        await message.reply_text("❌ সঠিক user ID দিন।")


@app.on_message(filters.command("unban") & owner_filter)
async def unban_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("ব্যবহার: <code>/unban user_id</code>")
    try:
        uid = int(message.command[1])
        BANNED_USERS.discard(uid)
        await banned_col.delete_one({"_id": uid})
        log_action(f"UNBAN: {uid}")
        await message.reply_text(f"✅ <code>{uid}</code> ব্যান মুক্ত।")
    except ValueError:
        await message.reply_text("❌ সঠিক user ID দিন।")


@app.on_message(filters.command("banlist") & owner_filter)
async def banlist_cmd(client, message: Message):
    if not BANNED_USERS:
        return await message.reply_text("📋 কেউ ব্যান নেই।")
    text = "🚫 <b>ব্যান লিস্ট:</b>\n\n"
    for uid in list(BANNED_USERS)[:50]:
        text += f"• <code>{uid}</code>\n"
    if len(BANNED_USERS) > 50:
        text += f"\n...আরও {len(BANNED_USERS) - 50} জন"
    await message.reply_text(text)


@app.on_message(filters.command("block") & owner_filter)
async def block_url_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text(
            "ব্যবহার: <code>/block pattern</code>\n"
            "উদাহরণ: <code>/block malicious\\.com</code>"
        )
    pattern = " ".join(message.command[1:])
    try:
        re.compile(pattern)  # validate regex
    except re.error:
        return await message.reply_text("❌ Invalid regex pattern")
    BLOCKED_PATTERNS.append(pattern)
    await blocked_urls_col.update_one(
        {"pattern": pattern}, {"$set": {"pattern": pattern}}, upsert=True
    )
    log_action(f"BLOCK URL: {pattern}")
    await message.reply_text(f"🔒 URL pattern ব্লক করা হয়েছে: <code>{pattern}</code>")


@app.on_message(filters.command("unblock") & owner_filter)
async def unblock_url_cmd(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("ব্যবহার: <code>/unblock pattern</code>")
    pattern = " ".join(message.command[1:])
    if pattern in BLOCKED_PATTERNS:
        BLOCKED_PATTERNS.remove(pattern)
    await blocked_urls_col.delete_one({"pattern": pattern})
    log_action(f"UNBLOCK URL: {pattern}")
    await message.reply_text(f"🔓 URL pattern আনব্লক: <code>{pattern}</code>")


@app.on_message(filters.command("logs") & owner_filter)
async def logs_cmd(client, message: Message):
    if not _LOG_BUFFER:
        return await message.reply_text("📋 কোনো সাম্প্রতিক লগ নেই।")
    text = "📋 <b>সাম্প্রতিক Security Logs:</b>\n\n"
    text += "\n".join(_LOG_BUFFER[-20:])
    await message.reply_text(f"<pre>{text}</pre>")


@app.on_message(filters.command("broadcast") & owner_filter)
async def broadcast_cmd(client, message: Message):
    if len(message.command) < 2 and not message.reply_to_message:
        return await message.reply_text("ব্যবহার: <code>/broadcast message</code>")

    text = (
        " ".join(message.command[1:])
        if len(message.command) > 1
        else message.reply_to_message.text
    )

    from MusicBangla.database import chatsdb
    chats = []
    async for doc in chatsdb.find():
        chats.append(doc["_id"])

    sent, failed = 0, 0
    status = await message.reply_text(f"📡 <b>ব্রডকাস্ট শুরু...</b> ({len(chats)} গ্রুপ)")

    for chat_id in chats:
        try:
            await app.send_message(chat_id, text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.5)  # flood control

    await status.edit(
        f"✅ <b>ব্রডকাস্ট সম্পূর্ণ</b>\n\n"
        f"📨 সফল: <code>{sent}</code>\n"
        f"❌ ব্যর্থ: <code>{failed}</code>"
    )
    log_action(f"BROADCAST: {sent} sent, {failed} failed")
