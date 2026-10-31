from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove
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

DIRECTION_MAP = {
    "dir_chorva": "chorva",
    "dir_parranda": "parranda",
}
