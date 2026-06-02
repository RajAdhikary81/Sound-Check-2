import asyncio
from pyrogram import filters
from pyrogram.types import Message

import config
from MusicBangla import app, calls, LOGGER
from MusicBangla.plugins.play import ACTIVE_CHATS, QUEUES, play_next_in_queue, _stop_progress, _SKIP_ACTIVE


async def react(client, message, emoji):
    try:
        await client.send_reaction(chat_id=message.chat.id, message_id=message.id, emoji=emoji)
    except Exception:
        pass


@app.on_message(filters.command("pause") & filters.group)
async def pause_cmd(client, message: Message):
    await react(client, message, "⏸")
    try:
        await calls.pause(message.chat.id)
        await message.reply_text("⏸ <b>গান পজ করা হলো।</b>")
    except Exception as e:
        LOGGER.error(e)
        await message.reply_text(f"{config.random_error_emoji()} পজ করা যাচ্ছে না — কোনো গান বাজছে কি?")


@app.on_message(filters.command("resume") & filters.group)
async def resume_cmd(client, message: Message):
    await react(client, message, "▶️")
    try:
        await calls.resume(message.chat.id)
        await message.reply_text("▶️ <b>গান আবার চালু হলো।</b>")
    except Exception as e:
        LOGGER.error(e)
        await message.reply_text(f"{config.random_error_emoji()} Resume করা যাচ্ছে না।")


@app.on_message(filters.command(["skip", "next"]) & filters.group)
async def skip_cmd(client, message: Message):
    """Skip current song — explicitly plays next from queue."""
    await react(client, message, "⏭")
    chat_id = message.chat.id
    queue = QUEUES.get(chat_id, [])
    _stop_progress(chat_id)

    try:
        # Mark skip as active so stream_end handler won't double-trigger
        _SKIP_ACTIVE.add(chat_id)

        try:
            await calls.leave_call(chat_id)
        except Exception:
            pass

        # Small delay to let stream_end fire and get ignored
        await asyncio.sleep(0.5)

        if queue:
            await message.reply_text(
                f"⏭ <b>স্কিপ!</b> পরবর্তী গান লোড হচ্ছে...\n"
                f"📋 কিউতে বাকি: {len(queue)} টি"
            )
            try:
                await message.reply_sticker(config.random_queue_sticker())
            except Exception:
                pass
            await play_next_in_queue(chat_id)
        else:
            ACTIVE_CHATS.pop(chat_id, None)
            await message.reply_text(
                "⏭ <b>গান স্কিপ করা হলো।</b>\n"
                "কিউ খালি। নতুন গান: <code>/play</code>"
            )

        _SKIP_ACTIVE.discard(chat_id)
    except Exception as e:
        _SKIP_ACTIVE.discard(chat_id)
        LOGGER.error(e)
        await message.reply_text(f"{config.random_error_emoji()} স্কিপ করা যাচ্ছে না।")


@app.on_message(filters.command(["stop", "end"]) & filters.group)
async def stop_cmd(client, message: Message):
    """Stop playback and clear queue."""
    await react(client, message, "🛑")
    chat_id = message.chat.id

    try:
        _stop_progress(chat_id)
        _SKIP_ACTIVE.add(chat_id)
        ACTIVE_CHATS.pop(chat_id, None)
        if chat_id in QUEUES:
            QUEUES[chat_id].clear()
        try:
            await calls.leave_call(chat_id)
        except Exception:
            pass
        await asyncio.sleep(0.3)
        _SKIP_ACTIVE.discard(chat_id)
        await message.reply_text(
            "🛑 <b>স্ট্রিম বন্ধ ও কিউ পরিষ্কার।</b>\n"
            "ধন্যবাদ গান উপভোগ করার জন্য 💝"
        )
        try:
            await message.reply_sticker(config.random_stop_sticker())
        except Exception:
            pass
    except Exception as e:
        _SKIP_ACTIVE.discard(chat_id)
        LOGGER.error(e)
        await message.reply_text(f"{config.random_error_emoji()} স্টপ করা যাচ্ছে না।")
