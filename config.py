import os
from dotenv import load_dotenv
from database import get_setting

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
GROUP_ID = os.getenv("GROUP_ID", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin777")
SECRET_KEY = os.getenv("SECRET_KEY", "fermamax_super_secret_key_2026")

if GROUP_ID:
    try:
        GROUP_ID = int(GROUP_ID)
    except ValueError:
        pass

if ADMIN_CHAT_ID:
    try:
        ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
    except ValueError:
        pass

async def get_effective_group_id():
    db_val = await get_setting("group_id")
    if db_val:
        try:
            return int(db_val)
        except ValueError:
            return db_val
    return GROUP_ID if GROUP_ID else None

async def get_effective_admin_chat_id():
    db_val = await get_setting("admin_chat_id")
    if db_val:
        try:
            return int(db_val)
        except ValueError:
            return db_val
    return ADMIN_CHAT_ID if ADMIN_CHAT_ID else None

