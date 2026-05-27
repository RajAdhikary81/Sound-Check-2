from pyrogram import filters
from pyrogram.types import Message

from MusicBangla import app, calls, LOGGER
from MusicBangla.plugins.play import ACTIVE_CHATS, QUEUES


async def react(client, message, emoji):
    try:
        await client.send_reaction(chat_id=message.chat.id, message_id=message.id, emoji=emoji)
    except Exception:
        pass


@app.on_message(filters.command("pause") & filters.group)
async def pause_cmd(client, message: Message):
    await react(client, message, "⏸")
    try:
        await calls.pause_stream(message.chat.id)
        await message.reply_text("⏸ <b>গান পজ করা হলো।</b>")
    except Exception as e:
        LOGGER.error(e)
        await message.reply_text("❌ পজ করা যাচ্ছে না — কোনো গান বাজছে কি?")


@app.on_message(filters.command("resume") & filters.group)
async def resume_cmd(client, message: Message):
    await react(client, message, "▶️")
    try:
        await calls.resume_stream(message.chat.id)
        await message.reply_text("▶️ <b>গান আবার চালু হলো।</b>")
    except Exception as e:
        LOGGER.error(e)
        await message.reply_text("❌ Resume করা যাচ্ছে না।")


@app.on_message(filters.command(["skip", "next"]) & filters.group)
async def skip_cmd(client, message: Message):
    """Skip current song — auto-plays next from queue via on_stream_end."""
    await react(client, message, "⏭")
    chat_id = message.chat.id
    queue = QUEUES.get(chat_id, [])

    try:
        # Leave call triggers on_stream_end which auto-plays next
        ACTIVE_CHATS.pop(chat_id, None)
        await calls.leave_call(chat_id)

        if queue:
            await message.reply_text(
                f"⏭ <b>স্কিপ!</b> পরবর্তী গান লোড হচ্ছে...\n"
                f"📋 কিউতে বাকি: {len(queue)} টি"
            )
        else:
            await message.reply_text(
                "⏭ <b>গান স্কিপ করা হলো।</b>\n"
                "কিউ খালি। নতুন গান: <code>/play</code>"
            )
    except Exception as e:
        LOGGER.error(e)
        await message.reply_text("❌ স্কিপ করা যাচ্ছে না।")


@app.on_message(filters.command(["stop", "end"]) & filters.group)
async def stop_cmd(client, message: Message):
    """Stop playback and clear queue."""
    await react(client, message, "🛑")
    chat_id = message.chat.id

    try:
        ACTIVE_CHATS.pop(chat_id, None)
        # Clear queue so on_stream_end doesn't auto-play
        if chat_id in QUEUES:
            QUEUES[chat_id].clear()
        await calls.leave_call(chat_id)
        await message.reply_text(
            "🛑 <b>স্ট্রিম বন্ধ ও কিউ পরিষ্কার।</b>\n"
            "ধন্যবাদ গান উপভোগ করার জন্য 💝"
        )
    except Exception as e:
        LOGGER.error(e)
        await message.reply_text("❌ স্টপ করা যাচ্ছে না।")
