import asyncio
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from MusicBangla import app
from MusicBangla.database import add_user, add_chat


def main_buttons():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ গ্রুপে যোগ করো", url=f"https://t.me/{app.me.username if app.me else 'YourBot'}?startgroup=true")],
            [
                InlineKeyboardButton("📢 চ্যানেল", url=config.SUPPORT_CHANNEL),
                InlineKeyboardButton("💬 সাপোর্ট", url=config.SUPPORT_GROUP),
            ],
            [
                InlineKeyboardButton("👨‍💻 মালিক", url=f"https://t.me/{config.OWNER_USERNAME}"),
                InlineKeyboardButton("📁 সোর্স", url=config.GITHUB_URL),
            ],
        ]
    )


async def safe_react(client, message, emoji):
    try:
        await client.send_reaction(chat_id=message.chat.id, message_id=message.id, emoji=emoji)
    except Exception:
        pass

  async def safe_sticker(message, sticker_id):
    try:
        await message.reply_sticker(sticker_id)
    except Exception:
        pass


@app.on_message(filters.command("start") & filters.private)
async def start_private(client, message: Message):
    await add_user(message.from_user.id)
    await safe_react(client, message, config.random_emoji())

    caption = (
        f"╭───❀ ✦ ❀───╮\n"
        f"   🎶 <b>স্বাগতম {message.from_user.mention}!</b>\n"
        f"╰───❀ ✦ ❀───╯\n\n"
        f"আমি <b>{app.me.first_name}</b> — তোমার নিজস্ব বাংলা মিউজিক বট 🎧\n\n"
        f"আমাকে যেকোনো গ্রুপে অ্যাডমিন করে যোগ করো, তারপর ভয়েস চ্যাটে গান বাজাও।\n\n"
        f"✨ <b>প্রধান কমান্ডস:</b>\n"
        f"▫️ <code>/play গানের নাম</code> — গান চালাও\n"
        f"▫️ <code>/pause</code> ⏸  <code>/resume</code> ▶️\n"
        f"▫️ <code>/skip</code> ⏭  <code>/stop</code> 🛑\n"
        f"▫️ <code>/ping</code> — বটের স্ট্যাটাস\n\n"
        f"💝 <b>মালিক:</b> @{config.OWNER_USERNAME}\n"
        f"📢 <b>চ্যানেল:</b> {config.SUPPORT_CHANNEL}"
    )
    await message.reply_photo(
        photo=config.random_image(),
        caption=caption,
        reply_markup=main_buttons(),
    )
  await message.reply_photo(
        photo=config.random_image(),
        caption=caption,
        reply_markup=main_buttons(),
    )
    await asyncio.sleep(0.3)
    await safe_sticker(message, config.random_start_sticker())

    try:
        await app.send_message(
            chat_id=config.LOG_GROUP_ID,
            text=(
                f"🎉 নতুন ইউজার!\n\n"
                f"👤 {message.from_user.mention}\n"
                f"🆔 <code>{message.from_user.id}</code>\n"
                f"📛 @{message.from_user.username}"
            ),
        )
    except Exception:
        pass


@app.on_message(filters.command("start") & filters.group)
async def start_group(client, message: Message):
    await add_chat(message.chat.id)
    await safe_react(client, message, config.random_emoji())

caption = (
        f"🎶 <b>হ্যালো {message.chat.title}!</b>\n\n"
        f"আমি <b>{app.me.first_name}</b> — তোমাদের বাংলা মিউজিক বট 🎧\n\n"
        f"▫️ <code>/play গানের নাম</code> দিয়ে শুরু করো\n"
        f"▫️ আমাকে অবশ্যই <b>অ্যাডমিন</b> করো (Voice Chat manage permission সহ)"
    )
    await message.reply_photo(photo=config.random_image(), caption=caption, reply_markup=main_buttons())


@app.on_message(filters.new_chat_members, group=-1)
async def welcome(client, message: Message):
    for member in message.new_chat_members:
        if member.id == app.me.id:
            await add_chat(message.chat.id)
            caption = (
                f"🎉 <b>ধন্যবাদ {message.from_user.first_name}!</b>\n\n"
                f"আমাকে <b>{message.chat.title}</b>-এ যোগ করার জন্য ❤️\n\n"
                f"✅ আমাকে <b>Admin</b> করো (Manage Voice Chats permission দাও)\n"
                f"✅ Assistant অ্যাকাউন্ট গ্রুপে যোগ করো\n"
                f"▫️ তারপর <code>/play গানের নাম</code> দিয়ে শুরু!"
            )
            try:
                await message.reply_photo(photo=config.random_image(), caption=caption, reply_markup=main_buttons())
                await safe_sticker(message, config.random_start_sticker())
            except Exception:
                await message.reply_text(caption)
