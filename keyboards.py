from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    WebAppInfo
)

def get_direction_keyboard() -> InlineKeyboardMarkup:
    """1-savol: Faqat 2 ta tugma (Chorva / Parranda)"""
    buttons = [
        [
            InlineKeyboardButton(text="🐄 Chorva", callback_data="dir_chorva"),
            InlineKeyboardButton(text="🐔 Parranda", callback_data="dir_parranda")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_phone_keyboard() -> ReplyKeyboardMarkup:
    """Ixtiyoriy telefon raqam qoldirish tugmalari"""
    buttons = [
        [KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)],
        [KeyboardButton(text="➡️ O'tkazib yuborish")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Doimiy pastda qadalib turuvchi asosiy menyu tugmalari"""
    buttons = [
        [
            KeyboardButton(text="👥 Do'stlarni taklif qilish"),
            KeyboardButton(text="📢 Yangiliklar")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        is_persistent=True
    )

def get_admin_main_keyboard(live_enabled: bool = True, webapp_url: str = "") -> ReplyKeyboardMarkup:
    """Administrator uchun maxsus pastki menyu tugmalari"""
    live_status = "🔔 Jonli xabarlar: Yoqilgan" if live_enabled else "🔕 Jonli xabarlar: O'chirilgan"
    
    app_btn = KeyboardButton(
        text="🚀 Admin Panel",
        web_app=WebAppInfo(url=webapp_url)
    ) if webapp_url else KeyboardButton(text="🌐 Admin Panel (Sayt)")

    buttons = [
        [
            KeyboardButton(text="📊 Statistika"),
            KeyboardButton(text=live_status)
        ],
        [
            app_btn,
            KeyboardButton(text="👥 Taklif havolasi olish")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        is_persistent=True
    )

DIRECTION_MAP = {
    "dir_chorva": "chorva",
    "dir_parranda": "parranda",
}
