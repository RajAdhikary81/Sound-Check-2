"""
🛠️ Utility functions for MusicBangla Bot
"""

import os
import asyncio
from typing import Optional
from MusicBangla import LOGGER


def ensure_downloads_folder():
    """✅ Downloads folder বিদ্যমান নিশ্চিত করুন"""
    try:
        os.makedirs("downloads", exist_ok=True)
        LOGGER.info("✅ Downloads folder ready")
        return True
    except Exception as e:
        LOGGER.error(f"❌ Downloads folder error: {e}")
        return False


def cleanup_downloads(max_age: int = 3600):
    """🧹 পুরানো ডাউনলোড ফাইল delete করুন (১ ঘণ্টার বেশি পুরানো)"""
    try:
        import time
        download_dir = "downloads"
        if not os.path.exists(download_dir):
            return
        
        current_time = time.time()
        deleted = 0
        
        for filename in os.listdir(download_dir):
            filepath = os.path.join(download_dir, filename)
            if os.path.isfile(filepath):
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age:
                    try:
                        os.remove(filepath)
                        deleted += 1
                    except Exception as e:
                        LOGGER.warning(f"Could not delete {filename}: {e}")
        
        if deleted > 0:
            LOGGER.info(f"🧹 Cleaned {deleted} old files")
    except Exception as e:
        LOGGER.warning(f"Cleanup error: {e}")


def format_seconds(seconds: int) -> str:
    """⏱️ সেকেন্ডকে MM:SS ফরম্যাটে রূপান্তর"""
    try:
        if not seconds:
            return "00:00"
        
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins:02d}:{secs:02d}"
    except Exception:
        return "00:00"


def format_bytes(bytes_val: int) -> str:
    """📊 Bytes-কে মানবিক ফরম্যাটে রূপান্তর"""
    try:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} TB"
    except Exception:
        return f"{bytes_val} B"


async def run_sync(func, *args, **kwargs):
    """⚡ Sync function-কে async-এ রান করুন"""
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args)
    except Exception as e:
        LOGGER.error(f"Sync execution error: {e}")
        return None


def get_file_size(filepath: str) -> Optional[int]:
    """📦 ফাইল সাইজ পান"""
    try:
        if os.path.exists(filepath):
            return os.path.getsize(filepath)
        return None
    except Exception as e:
        LOGGER.error(f"File size error: {e}")
        return None


def is_url(text: str) -> bool:
    """🔗 চেক করুন text URL কিনা"""
    try:
        return text.startswith(('http://', 'https://', 'www.'))
    except Exception:
        return False


def extract_user_id(message_text: str) -> Optional[int]:
    """👤 মেসেজ থেকে User ID বের করুন"""
    try:
        import re
        match = re.search(r'\d+', message_text)
        if match:
            return int(match.group())
        return None
    except Exception:
        return None


# ✅ স্টার্টআপ-এ চালান
if __name__ == "__main__":
    ensure_downloads_folder()
