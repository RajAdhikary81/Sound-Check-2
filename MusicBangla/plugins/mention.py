"""
সবাইকে mention/tag করার plugin।
- /tagall [optional message] — সব non-bot member কে mention
- /admins — গ্রুপের admin-দের mention
- /cancel — চলমান tag-all বন্ধ করা
"""
import asyncio
from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter
from pyrogram.types import Message

from MusicBangla import app, LOGGER


# chat_id -> bool (cancel requested)
CANCEL_TAGS: dict = {}
# chat_id -> bool (running)
RUNNING_TAGS: dict = {}


async def is_user_admin(client, chat_id: int, user_id: int) -> bool:
    try:
        m = await client.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


@app.on_message(filters.command(["tagall", "all", "mentionall"]) & filters.group)
async def tag_all(client, message: Message):
    chat_id = message.chat.id

    # Admin-only
    if not await is_user_admin(client, chat_id, message.from_user.id):
        return await message.reply_text("❌ এই কমান্ড শুধু গ্রুপের <b>admin</b>-রা ব্যবহার করতে পারবে।")

    if RUNNING_TAGS.get(chat_id):
        return await message.reply_text("⏳ একটি tag-all এখনো চলছে। থামাতে <code>/cancel</code> দাও।")

    # custom message
    custom = ""
    if len(message.command) > 1:
        custom = " ".join(message.command[1:])
    elif message.reply_to_message and message.reply_to_message.text:
        custom = message.reply_to_message.text

    header = "📣 <b>সবাইকে ডাকছি!</b>\n\n"
    if custom:
        header += f"💬 <b>মেসেজ:</b> {custom}\n\n"

    RUNNING_TAGS[chat_id] = True
    CANCEL_TAGS[chat_id] = False

    mentions = []
    count = 0
    batch_size = 5  # প্রতি মেসেজে ৫ জন (Telegram flood এড়াতে)

    try:
        async for member in client.get_chat_members(chat_id):
            if CANCEL_TAGS.get(chat_id):
                await message.reply_text("🛑 Tag-all বাতিল করা হলো।")
                break
            u = member.user
            if u.is_bot or u.is_deleted:
                continue
            mentions.append(f"• {u.mention}")
            count += 1

            if len(mentions) >= batch_size:
                text = header + "\n".join(mentions) if count <= batch_size else "\n".join(mentions)
                try:
                    await client.send_message(chat_id, text)
                except Exception as e:
                    LOGGER.warning(f"tagall batch send failed: {e}")
                mentions = []
                await asyncio.sleep(1.2)  # flood control

        # বাকি গুলো
        if mentions and not CANCEL_TAGS.get(chat_id):
            text = header + "\n".join(mentions) if count <= batch_size else "\n".join(mentions)
            try:
                await client.send_message(chat_id, text)
            except Exception as e:
                LOGGER.warning(f"tagall final send failed: {e}")

        if not CANCEL_TAGS.get(chat_id):
            await message.reply_text(f"✅ <b>মোট {count} জনকে mention করা হলো।</b>")
    except Exception as e:
        LOGGER.error(f"tagall error: {e}")
        await message.reply_text(f"❌ Tag-all এ সমস্যা: <code>{e}</code>")
    finally:
        RUNNING_TAGS[chat_id] = False
        CANCEL_TAGS[chat_id] = False


@app.on_message(filters.command("cancel") & filters.group)
async def cancel_tag(client, message: Message):
    chat_id = message.chat.id
    if not await is_user_admin(client, chat_id, message.from_user.id):
        return await message.reply_text("❌ শুধু admin বাতিল করতে পারবে।")
    if not RUNNING_TAGS.get(chat_id):
        return await message.reply_text("ℹ️ এখন কোনো tag-all চলছে না।")
    CANCEL_TAGS[chat_id] = True
    await message.reply_text("🛑 Tag-all থামানোর চেষ্টা করছি...")


@app.on_message(filters.command(["admins", "admin"]) & filters.group)
async def mention_admins(client, message: Message):
    chat_id = message.chat.id
    mentions = []
    try:
        async for m in client.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
            if m.user.is_bot:
                continue
            mentions.append(f"• {m.user.mention}")
    except Exception as e:
        return await message.reply_text(f"❌ Admin আনতে সমস্যা: <code>{e}</code>")

    if not mentions:
        return await message.reply_text("ℹ️ কোনো admin পাওয়া যায়নি।")

    text = "👮 <b>গ্রুপ Admin-গণ:</b>\n\n" + "\n".join(mentions)
    if message.reply_to_message:
        await message.reply_to_message.reply_text(text)
    else:
        await message.reply_text(text)
