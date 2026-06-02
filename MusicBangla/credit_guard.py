"""
╔══════════════════════════════════════════════════════════════════╗
║  MusicBangla — Credit Integrity Guard                           ║
║  মূল ডেভেলপার: @R4J_81 (https://github.com/RajSukh81)          ║
║                                                                  ║
║  এই ফাইল বট স্টার্টআপে ক্রেডিট ভেরিফাই করে।                  ║
║  ক্রেডিট পরিবর্তন করলে বট চালু হবে না।                         ║
║  This module verifies developer credit on every startup.         ║
║  Tampering with credit values will prevent the bot from running. ║
║                                                                  ║
║  DO NOT MODIFY THIS FILE.                                        ║
╚══════════════════════════════════════════════════════════════════╝
"""

import hashlib
import sys
import logging

LOGGER = logging.getLogger("MusicBangla.CreditGuard")

# ── Immutable credit constants ──────────────────────────────────
ORIGINAL_DEVELOPER = "R4J_81"
ORIGINAL_DEVELOPER_URL = "https://t.me/R4J_81"
ORIGINAL_GITHUB_USER = "RajSukh81"
ORIGINAL_REPO_URL = "https://github.com/RajSukh81/MusicBangla"
_EXPECTED_SIGNATURE = "R4J_81::RajSukh81::MusicBangla::2025"
_INTEGRITY_HASH = hashlib.sha256(_EXPECTED_SIGNATURE.encode()).hexdigest()


def verify_credit() -> bool:
    """
    বট স্টার্টআপে ক্রেডিট ইন্টিগ্রিটি চেক করে।
    config.py-এর DEVELOPER ভ্যালু পরিবর্তন করা হলে বট চালু হবে না।

    Returns True if credit is intact, exits the process otherwise.
    """
    try:
        import config
    except ImportError:
        LOGGER.critical("❌ config.py পাওয়া যায়নি! বট চালু অসম্ভব।")
        sys.exit(1)

    errors = []

    # Check 1: DEVELOPER_USERNAME
    if not hasattr(config, "DEVELOPER_USERNAME") or config.DEVELOPER_USERNAME != ORIGINAL_DEVELOPER:
        errors.append(
            f"DEVELOPER_USERNAME পরিবর্তন ধরা পড়েছে! "
            f"প্রত্যাশিত: '{ORIGINAL_DEVELOPER}', "
            f"পাওয়া গেছে: '{getattr(config, 'DEVELOPER_USERNAME', 'MISSING')}'"
        )

    # Check 2: DEVELOPER_URL
    if not hasattr(config, "DEVELOPER_URL") or config.DEVELOPER_URL != ORIGINAL_DEVELOPER_URL:
        errors.append(
            f"DEVELOPER_URL পরিবর্তন ধরা পড়েছে! "
            f"প্রত্যাশিত: '{ORIGINAL_DEVELOPER_URL}', "
            f"পাওয়া গেছে: '{getattr(config, 'DEVELOPER_URL', 'MISSING')}'"
        )

    # Check 3: Signature integrity
    sig = getattr(config, "_CREDIT_SIGNATURE", "")
    sig_hash = hashlib.sha256(sig.encode()).hexdigest()
    if sig_hash != _INTEGRITY_HASH:
        errors.append("_CREDIT_SIGNATURE integrity check ব্যর্থ! ক্রেডিট সিগনেচার টেম্পার করা হয়েছে।")

    # Check 4: DEVELOPER_GITHUB
    if not hasattr(config, "DEVELOPER_GITHUB") or config.DEVELOPER_GITHUB != f"https://github.com/{ORIGINAL_GITHUB_USER}":
        errors.append("DEVELOPER_GITHUB পরিবর্তন ধরা পড়েছে!")

    # Check 5: ORIGINAL_REPO
    if not hasattr(config, "ORIGINAL_REPO") or config.ORIGINAL_REPO != ORIGINAL_REPO_URL:
        errors.append("ORIGINAL_REPO পরিবর্তন ধরা পড়েছে!")

    if errors:
        LOGGER.critical("=" * 70)
        LOGGER.critical("🚨 ক্রেডিট ইন্টিগ্রিটি লঙ্ঘন সনাক্ত হয়েছে! 🚨")
        LOGGER.critical("=" * 70)
        for err in errors:
            LOGGER.critical(f"  ❌ {err}")
        LOGGER.critical("")
        LOGGER.critical(f"  MusicBangla-এর মূল ডেভেলপার: @{ORIGINAL_DEVELOPER}")
        LOGGER.critical(f"  GitHub: {ORIGINAL_REPO_URL}")
        LOGGER.critical("")
        LOGGER.critical("  ⚠️  ক্রেডিট পরিবর্তন করা লাইসেন্স লঙ্ঘন।")
        LOGGER.critical("  ⚠️  বট চালু হবে না যতক্ষণ না ক্রেডিট পুনরুদ্ধার করা হয়।")
        LOGGER.critical("  ⚠️  অনুগ্রহ করে config.py-তে মূল ডেভেলপার ক্রেডিট ফিরিয়ে আনুন।")
        LOGGER.critical("=" * 70)
        sys.exit(1)

    LOGGER.info(f"✅ ক্রেডিট ভেরিফাইড — মূল ডেভেলপার: @{ORIGINAL_DEVELOPER}")
    return True


def get_credit_text() -> str:
    """বটের ক্রেডিট টেক্সট রিটার্ন করে — সব /start, /help মেসেজে ব্যবহৃত হয়।"""
    return (
        f"🧑‍💻 <b>ডেভেলপার:</b> <a href='{ORIGINAL_DEVELOPER_URL}'>@{ORIGINAL_DEVELOPER}</a>\n"
        f"📁 <b>সোর্স:</b> <a href='{ORIGINAL_REPO_URL}'>MusicBangla on GitHub</a>"
    )


def get_credit_footer() -> str:
    """ছোট ক্রেডিট ফুটার — বিভিন্ন মেসেজে ব্যবহারের জন্য।"""
    return f"⚡ Powered by <a href='{ORIGINAL_REPO_URL}'>MusicBangla</a> | Dev: @{ORIGINAL_DEVELOPER}"
