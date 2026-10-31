import logging
import os
import time
import re
from typing import Union
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.types import (
    Message, 
    CallbackQuery, 
    ChatMemberUpdated,
    ReplyKeyboardRemove, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    FSInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import get_effective_group_id, get_effective_admin_chat_id
from database import (
    save_response, 
    get_response, 
    get_user_by_id,
    set_setting, 
    update_phone_number, 
    get_stats, 
    get_recent_responses,
    get_all_responses,
    save_invite_link,
    get_invite_link,
    mark_invite_link_used,
    record_group_join,
    get_user_referrals,
    get_user_referral_count,
    get_top_referrers,
    get_group_joins,
    get_or_create_referral_code,
    resolve_referral_code,
    mask_user_id
)
from keyboards import get_direction_keyboard, get_phone_keyboard, get_main_menu_keyboard, DIRECTION_MAP
from states import CustDevStates
from export_csv import export_to_csv, OUTPUT_CSV
from analytics import analyze_custdev, CATEGORIES

logger = logging.getLogger(__name__)
router = Router()

VOICE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices")
os.makedirs(VOICE_DIR, exist_ok=True)

async def save_voice(bot: Bot, voice, user_id: int, label: str) -> tuple[str, str]:
    """
    Ovozli xabarni Telegramdan yuklab oladi va voices/ jildida saqlaydi.
    Shuningdek Safari va barcha brauzerlar uchun avtomatik WAV formatiga ham o'giradi.
    Qaytaradi: (file_id, filename)
    """
    file_id = voice.file_id
    filename = f"{user_id}_{label}_{int(time.time())}.ogg"
    filepath = os.path.join(VOICE_DIR, filename)
    try:
        file_obj = await bot.get_file(file_id)
        if file_obj.file_path:
            await bot.download_file(file_obj.file_path, destination=filepath)
            
            # Safari / barcha brauzerlar uchun avtomatik WAV ga o'girish (macOS da afconvert, Linuxda ffmpeg)
            wav_path = os.path.splitext(filepath)[0] + ".wav"
            if os.path.exists(filepath):
                import subprocess
                import shutil
                if os.path.exists("/usr/bin/afconvert"):
                    subprocess.run(
                        ["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16", filepath, wav_path],
                        capture_output=True
                    )
                elif shutil.which("ffmpeg"):
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", filepath, wav_path],
                        capture_output=True
                    )
            return file_id, filename
    except Exception as e:
        logger.error(f"Voice yuklab olishda xatolik: {e}")
    return file_id, ""

# ==================== GURUHGA QO'SHILGANLAR VA XIZMAT XABARLARI ====================

@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def handle_new_member_join(event: ChatMemberUpdated, bot: Bot):
    """Foydalanuvchi bir martalik havola yoki boshqa yo'l bilan guruhga qo'shilganda"""
    new_member = event.new_chat_member.user
    if new_member.is_bot:
        return

    invite_link_str = event.invite_link.invite_link if event.invite_link else None
    creator_user_id = None
    inviter_name = None

    if invite_link_str:
        link_info = await get_invite_link(invite_link_str)
        if link_info:
            creator_user_id = link_info.get("creator_user_id")
            await mark_invite_link_used(
                invite_link_str, 
                used_by_user_id=new_member.id, 
                used_by_name=new_member.full_name
            )
            if creator_user_id:
                inviter = await get_user_by_id(creator_user_id)
                if inviter:
                    inviter_name = inviter.get("full_name")

    await record_group_join(
        user_id=new_member.id,
        full_name=new_member.full_name or "Fermer",
        username=new_member.username or "",
        invited_by=creator_user_id,
        invite_link=invite_link_str
    )

    # Adminga bildirishnoma yuborish
    admin_chat_id = await get_effective_admin_chat_id()
    if admin_chat_id:
        ref_text = f"\n👥 **Taklif qilgan:** {inviter_name} (`{creator_user_id}`)" if inviter_name else ""
        link_text = f"\n🔗 **Ishlatilgan havola:** `{invite_link_str}`" if invite_link_str else ""
        join_msg = (
            "🎉 **Guruhga yangi fermer qo'shildi!**\n\n"
            f"👤 **Fermer:** {new_member.full_name} (@{new_member.username or 'yo`q'})\n"
            f"🆔 **ID:** `{new_member.id}`"
            f"{ref_text}"
            f"{link_text}"
        )
        try:
            await bot.send_message(chat_id=admin_chat_id, text=join_msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Adminga join xabarini yuborishda xatolik: {e}")

    # Taklif qilgan fermerga xushxabar berish
    if creator_user_id and creator_user_id != new_member.id:
        try:
            await bot.send_message(
                chat_id=creator_user_id,
                text=(
                    f"🎉 **Ajoyib yangilik!**\n\n"
                    f"Siz taklif qilgan do'stingiz **{new_member.full_name}** Fermerlar Klubiga muvaffaqiyatli qo'shildi! "
                    "Klubimizni birgalikda rivojlantirayotganingiz uchun rahmat! 🤝"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.debug(f"Referrerga xushxabar yuborilmadi: {e}")

@router.message(F.new_chat_members)
async def auto_delete_join_messages(message: Message):
    """Guruhga qo'shildi xabarlarini avtomatik o'chirish va bazada qayd etish"""
    try:
        await message.delete()
    except Exception:
        pass

    for user in message.new_chat_members:
        if not user.is_bot:
            await record_group_join(
                user_id=user.id,
                full_name=user.full_name or "Fermer",
                username=user.username or "",
                invited_by=None,
                invite_link=None
            )

@router.message(F.left_chat_member)
async def auto_delete_left_messages(message: Message):
    """Guruhdan chiqdi xabarlarini avtomatik o'chirish"""
    try:
        await message.delete()
    except Exception:
        pass

# ==================== ID SOZLASH (/id) ====================

@router.message(Command("id"))
async def cmd_get_id(message: Message, bot: Bot):
    chat = message.chat
    user = message.from_user
    username = user.username or user.full_name

    if chat.type in ("group", "supergroup"):
        await set_setting("group_id", str(chat.id))
        await set_setting("admin_chat_id", str(user.id))

        await message.reply(
            "✅ **Sozlamalar avtomatik saqlandi!**\n\n"
            f"📌 **Guruh ID:** `{chat.id}` (Fermerlar Klubi guruhi)\n"
            f"👤 **Admin ID:** `{user.id}` (@{username})\n\n"
            "✨ *Endi bot anketani to'ldirgan har bir fermer uchun ushbu guruhga 1 martalik havola beradi "
            "va to'ldirilgan javoblarni sizning shaxsiyingizga yuboradi!*",
            parse_mode="Markdown"
        )
    else:
        await set_setting("admin_chat_id", str(user.id))
        
        group_id = await get_effective_group_id()
        group_status = f"`{group_id}`" if group_id else "*Hali belgilanmagan*"

        await message.reply(
            "✅ **Admin ID saqlandi!**\n\n"
            f"👤 **Sizning ID:** `{user.id}` (@{username})\n"
            f"📌 **Hozirgi guruh ID:** {group_status}\n\n"
            "👉 **Guruhni ulash uchun:**\n"
            "1. Botni **Fermerlar Klubi** guruhiga qo'shing va **Admin** qiling.\n"
            "2. O'sha guruh ichida `/id` deb yozing.\n"
            "Shunda bot guruhni ham avtomatik o'ziga bog'lab oladi!",
            parse_mode="Markdown"
        )

# ==================== FOYDALANUVCHI OQIMI (/start & CustDev) ====================

async def is_user_in_group(bot: Bot, user_id: int) -> bool:
    """Foydalanuvchi guruhda bor-yo'qligini tekshiradi."""
    group_id = await get_effective_group_id()
    if not group_id:
        return False
    try:
        member = await bot.get_chat_member(chat_id=group_id, user_id=user_id)
        if member.status in ("creator", "administrator", "member", "restricted"):
            return True
        return False
    except TelegramBadRequest:
        return False
    except Exception as e:
        logger.error(f"Guruh a'zoligini tekshirishda xatolik: {e}")
        return False

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot, command: CommandObject = None):
    user = message.from_user
    if not user:
        return

    # 0. Admin tekshiruvi: Agar foydalanuvchi Admin bo'lsa, unga anketa berilmaydi!
    admin_chat_id = await get_effective_admin_chat_id()
    if admin_chat_id and str(user.id) == str(admin_chat_id):
        await state.clear()
        stats = await get_stats()
        group_id = await get_effective_group_id()
        group_status = f"`{group_id}`" if group_id else "*Hali belgilanmagan*"
        
        admin_text = (
            "👑 **Assalomu alaykum, Hurmatli Administrator!**\n\n"
            "Siz botning boshqaruvchisisiz. Sizga oddiy foydalanuvchilar kabi anketalar berilmaydi.\n"
            "Yangi fermerlar anketa to'ldirganda va guruhga qo'shilganda bot barcha ma'lumot va ovozli xabarlarni sizga yuborib turadi.\n\n"
            f"📊 **Hozirgi statistika:**\n"
            f"• Jami anketalar: **{stats['total']} ta**\n"
            f"• Guruhga qo'shilganlar: **{stats['group_joins_count']} ta**\n"
            f"• Telefon qoldirganlar: **{stats['with_phone']} ta**\n"
            f"• Ovozli xabarlar: **{stats['with_voice']} ta**\n\n"
            f"📌 **Ulangan guruh ID:** {group_status}\n"
            "*(Guruhni ulash yoki almashtirish uchun o'sha guruh ichida `/id` deb yozing)*"
        )
        admin_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Statistikani yangilash", callback_data="admin_refresh_stats")],
            [InlineKeyboardButton(text="👥 Taklif havolasini olish", callback_data="btn_invite_friends")]
        ])
        await message.answer(admin_text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
        await message.answer("🛠 Boshqaruv vositalari:", reply_markup=admin_kb)
        return

    # Maxfiy referral kodini tekshirish (masalan: /start c_8f1b2c3d yoki ref_c_8f1b2c3d)
    referrer_id = None
    if command and command.args:
        args = command.args.strip()
        resolved = await resolve_referral_code(args)
        if resolved and resolved != user.id:
            referrer_id = resolved

    # Guruhda bormi yo'qmi tekshirish
    already_member = await is_user_in_group(bot, user.id)
    if already_member:
        await state.clear()
        ref_count = await get_user_referral_count(user.id)
        await message.answer(
            "Assalomu alaykum! 🤝\n\n"
            "Siz allaqachon **Fermerlar Klubi** a'zosisiz! "
            "Guruhimizda faol bo'ling va boshqa fermerlar bilan tajriba almashing.\n\n"
            f"📊 *Siz taklif qilgan fermerlar:* **{ref_count} ta**",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
        return

    # CustDev anketasini boshlash
    await state.clear()
    if referrer_id:
        await state.update_data(referred_by=referrer_id)
    
    welcome_text = (
        "Assalomu alaykum! 🌾 Fermerlar klubiga xush kelibsiz.\n"
        "Guruhga kirishdan oldin atigi **4 ta qisqa savol**, 2 daqiqa. "
        "Javoblaringiz asosida sizga kerakli narsalarni tayyorlaymiz.\n\n"
        "**1-savol:** Qaysi yo'nalishda ishlaysiz?"
    )
    await message.answer(welcome_text, reply_markup=get_direction_keyboard(), parse_mode="Markdown")
    await state.set_state(CustDevStates.direction)

# 1-savol: Chorva yoki Parranda tanlanganda
@router.callback_query(CustDevStates.direction, F.data.startswith("dir_"))
async def process_direction(callback: CallbackQuery, state: FSMContext):
    direction_key = callback.data
    direction_val = DIRECTION_MAP.get(direction_key, "chorva")
    
    await state.update_data(direction=direction_val)
    await callback.answer()

    if direction_val == "chorva":
        question_1b = (
            "Tanlangan yo'nalish: **🐄 Chorva**\n\n"
            "**1-b.** Nechta bosh mol, qo'y yoki echkingiz bor? *(raqam yozsangiz kifoya)*"
        )
    else:
        question_1b = (
            "Tanlangan yo'nalish: **🐔 Parranda**\n\n"
            "**1-b.** Nechta tovuq yoki boshqa parrandangiz bor? *(raqam yozsangiz kifoya)*"
        )
    
    await callback.message.edit_text(question_1b, parse_mode="Markdown")
    await state.set_state(CustDevStates.livestock_count)

# 1-savol: Tugma bosmasdan matn yoki ovoz yuborilsa
@router.message(CustDevStates.direction)
async def prompt_direction_choice(message: Message):
    await message.answer(
        "Iltimos, yo'nalishingizni quyidagi tugmalardan birini bosib tanlang: 👇",
        reply_markup=get_direction_keyboard()
    )

# 1-b savoli: Bosh soni yozilganda yoki ovozli yuborilganda
@router.message(CustDevStates.livestock_count, F.text | F.voice | F.audio)
async def process_livestock_count(message: Message, state: FSMContext, bot: Bot):
    if message.voice or message.audio:
        audio_obj = message.voice or message.audio
        voice_id, voice_path = await save_voice(bot, audio_obj, message.from_user.id, "livestock")
        await state.update_data(livestock_count="[🎙 Ovozli xabar]")
    else:
        count_text = message.text.strip()
        await state.update_data(livestock_count=count_text)
    
    data = await state.get_data()
    direction = data.get("direction", "chorva")
    
    if direction == "chorva":
        question_2 = (
            "Rahmat 🙏 Keyingi savol (2/4):\n\n"
            "**2-savol.** Oxirgi 1-2 oyda chorvangizda sizni eng ko'p qiynagan holat nima bo'ldi? "
            "Oxirgi marta qachon bo'lganini ham yozing.\n"
            "*(Masalan: mol kasal bo'ldi, sut kamaydi, em yoki pichan qimmat bo'ldi, mahsulotni sota olmadingiz)*\n\n"
            "🎙 *Matn yoki ovozli xabar ko'rinishida yuborishingiz mumkin.*"
        )
    else:
        question_2 = (
            "Rahmat 🙏 Keyingi savol (2/4):\n\n"
            "**2-savol.** Oxirgi 1-2 oyda parrandachilikda sizni eng ko'p qiynagan holat nima bo'ldi? "
            "Oxirgi marta qachon bo'lganini ham yozing.\n"
            "*(Masalan: parranda kasal bo'ldi yoki nobud bo'ldi, em qimmat bo'ldi, tuxum yoki go'shtni sota olmadingiz, jo'ja topish qiyin bo'ldi)*\n\n"
            "🎙 *Matn yoki ovozli xabar ko'rinishida yuborishingiz mumkin.*"
        )
    
    await message.answer(question_2, parse_mode="Markdown")
    await state.set_state(CustDevStates.problem)

# 2-savol: Muammo qabul qilinganda (Matn yoki Ovozli)
@router.message(CustDevStates.problem, F.text | F.voice)
async def process_problem(message: Message, state: FSMContext, bot: Bot):
    if message.voice:
        voice_id, voice_path = await save_voice(bot, message.voice, message.from_user.id, "problem")
        await state.update_data(
            problem="[🎙 Ovozli xabar]", 
            problem_voice_id=voice_id,
            problem_voice_path=voice_path
        )
    else:
        await state.update_data(problem=message.text, problem_voice_id="", problem_voice_path="")
        
    data = await state.get_data()
    direction = data.get("direction", "chorva")
    
    if direction == "chorva":
        question_3 = (
            "Tushundim, rahmat 🙏 (3/4)\n\n"
            "**3-savol.** O'sha holatda nima qildingiz? Kimdan yordam so'radingiz (veterinar, qo'shni, internet) "
            "va taxminan qancha pul yoki vaqt ketdi?\n\n"
            "🎙 *Matn yoki ovozli xabar ko'rinishida yuborishingiz mumkin.*"
        )
    else:
        question_3 = (
            "Tushundim, rahmat 🙏 (3/4)\n\n"
            "**3-savol.** O'sha holatda nima qildingiz? Kimdan yordam so'radingiz (veterinar, em sotuvchi, qo'shni, internet) "
            "va taxminan qancha pul yoki vaqt ketdi?\n\n"
            "🎙 *Matn yoki ovozli xabar ko'rinishida yuborishingiz mumkin.*"
        )
        
    await message.answer(question_3, parse_mode="Markdown")
    await state.set_state(CustDevStates.solution_taken)

# 3-savol: Yechim va xarajat qabul qilinganda (Matn yoki Ovozli)
@router.message(CustDevStates.solution_taken, F.text | F.voice)
async def process_solution(message: Message, state: FSMContext, bot: Bot):
    if message.voice:
        voice_id, voice_path = await save_voice(bot, message.voice, message.from_user.id, "solution")
        await state.update_data(
            solution_taken="[🎙 Ovozli xabar]", 
            solution_voice_id=voice_id,
            solution_voice_path=voice_path
        )
    else:
        await state.update_data(solution_taken=message.text, solution_voice_id="", solution_voice_path="")
        
    question_4 = (
        "Juda foydali ma'lumot, rahmat! Oxirgi savol (4/4):\n\n"
        "**4-savol.** Qilgan yechimingiz to'liq yordam berdimi? Nima yetishmadi? "
        "Buni osonlashtirish uchun yana nima qidirgansiz yoki sinab ko'rgansiz?\n\n"
        "🎙 *Matn yoki ovozli xabar ko'rinishida yuborishingiz mumkin.*"
    )
    await message.answer(question_4, parse_mode="Markdown")
    await state.set_state(CustDevStates.dissatisfaction)

# 4-savol: Yakuniy savol qabul qilinganda -> Havola berish va Telefon so'rash
@router.message(CustDevStates.dissatisfaction, F.text | F.voice)
async def process_dissatisfaction(message: Message, state: FSMContext, bot: Bot):
    if message.voice:
        voice_id, voice_path = await save_voice(bot, message.voice, message.from_user.id, "dissatisfaction")
        await state.update_data(
            dissatisfaction="[🎙 Ovozli xabar]", 
            dissatisfaction_voice_id=voice_id,
            dissatisfaction_voice_path=voice_path
        )
    else:
        await state.update_data(dissatisfaction=message.text, dissatisfaction_voice_id="", dissatisfaction_voice_path="")
        
    data = await state.get_data()
    user = message.from_user
    
    user_id = user.id
    full_name = user.full_name or ""
    username = user.username or ""
    direction = data.get("direction", "chorva")
    livestock_count = data.get("livestock_count", "")
    problem = data.get("problem", "")
    problem_voice_id = data.get("problem_voice_id", "")
    problem_voice_path = data.get("problem_voice_path", "")
    solution_taken = data.get("solution_taken", "")
    solution_voice_id = data.get("solution_voice_id", "")
    solution_voice_path = data.get("solution_voice_path", "")
    dissatisfaction = data.get("dissatisfaction", "")
    dissatisfaction_voice_id = data.get("dissatisfaction_voice_id", "")
    dissatisfaction_voice_path = data.get("dissatisfaction_voice_path", "")
    referred_by = data.get("referred_by")

    # Bazaga saqlash
    await save_response(
        user_id=user_id,
        full_name=full_name,
        username=username,
        direction=direction,
        livestock_count=livestock_count,
        problem=problem,
        problem_voice_id=problem_voice_id,
        problem_voice_path=problem_voice_path,
        solution_taken=solution_taken,
        solution_voice_id=solution_voice_id,
        solution_voice_path=solution_voice_path,
        dissatisfaction=dissatisfaction,
        dissatisfaction_voice_id=dissatisfaction_voice_id,
        dissatisfaction_voice_path=dissatisfaction_voice_path,
        referred_by=referred_by
    )

    # Guruhga 1 martalik link yaratish
    group_id = await get_effective_group_id()
    admin_chat_id = await get_effective_admin_chat_id()

    invite_link = None
    if group_id:
        try:
            chat_invite = await bot.create_chat_invite_link(
                chat_id=group_id,
                member_limit=1,
                name=f"Fermer: {full_name[:20]}"
            )
            invite_link = chat_invite.invite_link
            await save_invite_link(invite_link, user_id, invite_type="custdev_complete")
        except Exception as e:
            logger.error(f"Taklif havolasi yaratishda xatolik: {e}")

    link_display = invite_link if invite_link else "(Guruh havolasi sozlanmoqda)"

    success_msg = (
        "Rahmat, barcha savollarga javob berdingiz! 🙏\n\n"
        f"Mana klubga kirish linki (faqat siz uchun bir martalik):\n🔗 **{link_display}**\n\n"
        "Ixtiyoriy: sizga mos yechim tayyorlaganimizda xabar berishimiz uchun "
        "telefon raqamingizni qoldirishingiz mumkin."
    )
    
    post_survey_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Do'stni taklif qilish (1 martalik havola)", callback_data="btn_invite_friends")]
    ])

    await message.answer(success_msg, reply_markup=get_phone_keyboard(), parse_mode="Markdown")
    await message.answer(
        "Fermer do'stingiz bormi? Uni ham klubimizga taklif qiling! 👇", 
        reply_markup=post_survey_kb
    )
    await state.set_state(CustDevStates.phone)

    # Adminga yangi anketa hisobotini yuborish
    if admin_chat_id:
        direction_badge = "🐄 Chorva" if direction == "chorva" else "🐔 Parranda"
        ref_line = f"\n🔗 **Taklif qilgan:** `{referred_by}`" if referred_by else ""
        admin_report = (
            "📋 **Yangi fermer anketa to'ldirdi!**\n\n"
            f"👤 **Fermer:** {full_name} "
            f"({'@' + username if username else 'username yo`q'})\n"
            f"🆔 **Telegram ID:** `{user_id}`\n"
            f"🏷 **Yo'nalish:** {direction_badge}\n"
            f"🔢 **Hajm (bosh soni):** {livestock_count}"
            f"{ref_line}\n\n"
            f"📌 **2-savol (Muammo):**\n{problem}\n\n"
            f"🛠 **3-savol (Yechim & Xarajat):**\n{solution_taken}\n\n"
            f"❓ **4-savol (Yetishmagan jihat):**\n{dissatisfaction}"
        )
        try:
            await bot.send_message(chat_id=admin_chat_id, text=admin_report, parse_mode="Markdown")
            
            if problem_voice_id:
                await bot.send_voice(
                    chat_id=admin_chat_id,
                    voice=problem_voice_id,
                    caption=f"🎙 2-savol javobi (ovozli) — {full_name}"
                )
            if solution_voice_id:
                await bot.send_voice(
                    chat_id=admin_chat_id,
                    voice=solution_voice_id,
                    caption=f"🎙 3-savol javobi (ovozli) — {full_name}"
                )
            if dissatisfaction_voice_id:
                await bot.send_voice(
                    chat_id=admin_chat_id,
                    voice=dissatisfaction_voice_id,
                    caption=f"🎙 4-savol javobi (ovozli) — {full_name}"
                )
        except Exception as e:
            logger.error(f"Adminga hisobot yuborishda xatolik: {e}")

from urllib.parse import quote_plus

def validate_phone(text: str) -> Union[str, None]:
    if not text:
        return None
    cleaned = re.sub(r"[^\d+]", "", text.strip())
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 9 or len(digits) > 15:
        return None
    if digits.startswith("998") and len(digits) == 12:
        return f"+{digits}"
    elif len(digits) == 9:
        return f"+998{digits}"
    elif cleaned.startswith("+"):
        return cleaned
    return f"+{digits}"

# Telefon raqami yuborilganda yoki o'tkazib yuborilganda
@router.message(CustDevStates.phone)
async def process_phone(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    user_id = user.id

    # 1. O'tkazib yuborish tanlanganda
    if message.text and ("o'tkazib" in message.text.lower() or "otkazib" in message.text.lower()):
        await message.answer(
            "Tushundim, klubda ko'rishguncha! 🤝",
            reply_markup=get_main_menu_keyboard()
        )
        await state.clear()
        return

    # 2. Kontakt tugmasi orqali yuborilganda
    phone_number = None
    if message.contact:
        phone_number = validate_phone(message.contact.phone_number) or message.contact.phone_number
    elif message.text:
        phone_number = validate_phone(message.text)

    # 3. Agar noto'g'ri matn yozilgan bo'lsa (masalan: 's')
    if not phone_number:
        await message.answer(
            "⚠️ **Iltimos, to'g'ri telefon raqam kiriting** (masalan: `+998901234567`) "
            "yoki quyidagi **'➡️ O'tkazib yuborish'** tugmasini bosing.",
            reply_markup=get_phone_keyboard(),
            parse_mode="Markdown"
        )
        return  # Holatdan chiqmaydi, qayta so'raydi

    # 4. To'g'ri telefon raqam saqlash
    await update_phone_number(user_id, phone_number)
    await message.answer(
        "Rahmat, telefon raqamingiz qabul qilindi! Klubda ko'rishguncha. 🤝",
        reply_markup=get_main_menu_keyboard()
    )
    await state.clear()

    admin_chat_id = await get_effective_admin_chat_id()
    if admin_chat_id:
        try:
            await bot.send_message(
                chat_id=admin_chat_id,
                text=f"📞 **Fermer telefon raqamini qoldirdi:**\n👤 {user.full_name}\n📱 `{phone_number}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Telefon raqamini adminga yuborishda xatolik: {e}")

# ==================== DO'STLARNI TAKLIF QILISH (REFERRAL TIZIMI) ====================

@router.message(F.text == "👥 Do'stlarni taklif qilish")
@router.callback_query(F.data == "btn_invite_friends")
@router.message(Command("taklif"))
@router.message(Command("invite"))
async def handle_invite_friends(event: Union[CallbackQuery, Message], bot: Bot):
    """Fermer do'stini taklif qilishi uchun 1 martalik havola yaratib berish (User ID maxfiy)"""
    user = event.from_user
    group_id = await get_effective_group_id()

    if not group_id:
        text = "Kechirasiz, klub guruhi hozircha sozlanmagan. Iltimos admin bilan bog'laning."
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)
        return

    # 1 martalik taklif havolasini yaratish
    invite_link = None
    try:
        chat_invite = await bot.create_chat_invite_link(
            chat_id=group_id,
            member_limit=1,
            name=f"Taklif: {user.full_name[:15]}"
        )
        invite_link = chat_invite.invite_link
        await save_invite_link(invite_link, user.id, invite_type="friend_referral")
    except Exception as e:
        logger.error(f"Do'st taklif havolasi yaratishda xatolik: {e}")

    # MAXFIY REFERRAL KODI (User ID mutlaqo ochiqlanmaydi!)
    secret_code = await get_or_create_referral_code(user.id)
    bot_info = await bot.get_me()
    bot_ref_link = f"https://t.me/{bot_info.username}?start={secret_code}"
    ref_count = await get_user_referral_count(user.id)

    share_text = quote_plus("🌾 Fermerlar Klubiga marhamat! Chorvachilik va parrandachilik bo'yicha yopiq klubga qo'shiling:")
    share_url = f"https://t.me/share/url?url={bot_ref_link}&text={share_text}"

    one_time_text = f"`{invite_link}`" if invite_link else "(Havola yaratilmadi, qaytadan urinib ko'ring)"

    msg_text = (
        "🤝 **Fermerlar Klubiga do'stingizni taklif qiling!**\n\n"
        "Quyidagi havola faqat **1 nafar do'stingiz** uchun bir martalik havoladir. "
        "Do'stingiz ushbu link orqali guruhga qo'shilishi bilan havola o'z kuchini yo'qotadi va siz taklif qilganingiz qayd etiladi:\n\n"
        f"🔗 **Do'stingiz uchun 1 martalik havola:**\n{one_time_text}\n\n"
        "👉 **Yoki bot orqali taklif havolasi (maxfiy):**\n"
        f"`{bot_ref_link}`\n"
        "*(Do'stingiz ham anketa to'ldirib klubga qo'shiladi)*\n\n"
        f"📊 *Siz hozirgacha taklif qilgan fermerlar:* **{ref_count} ta**"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Do'stlarga ulashish (Telegramda yuborish)", url=share_url)],
        [InlineKeyboardButton(text="🔄 Yangi 1 martalik havola olish", callback_data="btn_invite_friends")]
    ])

    if isinstance(event, CallbackQuery):
        await event.message.answer(msg_text, reply_markup=kb, parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(msg_text, reply_markup=kb, parse_mode="Markdown")

# ==================== YANGILIKLAR ====================

@router.message(F.text == "📢 Yangiliklar")
async def handle_news(message: Message):
    text = (
        "📢 **Fermerlar Klubi — Yangiliklar & E'lonlar**\n\n"
        "🌾 **Klubimizda yaqinda:**\n"
        "• 🐄 **Jonli efir**: Tajribali veterinar bilan qishki parvarish va ozuqa ratsioni bo'yicha savol-javob.\n"
        "• 🌾 **Em-xashak ta'minoti**: Sifatli yem va qo'shimchalar yetkazib beruvchilar bazasi.\n"
        "• 🤝 **Tajriba almashish**: Har haftalik faol muhokamalar guruhimizda davom etmoqda.\n\n"
        "✨ *Barcha tafsilotlar va yangiliklar yopiq guruhimizda e'lon qilib boriladi!*"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

# ==================== SODDA ADMIN PANEL (/admin) ====================

def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Muammolar tahlili (CustDev)", callback_data="admin_custdev_insights")],
        [InlineKeyboardButton(text="👥 Guruh a'zolari va Takliflar", callback_data="admin_referrals_stats")],
        [InlineKeyboardButton(text="📥 Excel (CSV) yuklab olish", callback_data="admin_download_csv")],
        [InlineKeyboardButton(text="📋 Oxirgi javoblarni ko'rish", callback_data="admin_recent_0")],
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_refresh")]
    ])

@router.message(Command("admin"))
async def cmd_admin(message: Message, bot: Bot):
    admin_id = await get_effective_admin_chat_id()
    if not admin_id or message.from_user.id != admin_id:
        await message.answer("Kechirasiz, siz bot administratori emassiz.")
        return

    stats = await get_stats()
    text = (
        "📊 **Fermerlar Klubi — CustDev & Referrals Admin Panel**\n\n"
        f"👥 **Jami anketalar:** {stats['total']} ta\n"
        f"🐄 **Chorvachilik:** {stats['chorva']} ta\n"
        f"🐔 **Parrandachilik:** {stats['parranda']} ta\n"
        f"📱 **Telefon qoldirganlar:** {stats['with_phone']} ta\n"
        f"🎙 **Ovozli xabar qoldirganlar:** {stats['with_voice']} ta\n"
        f"🚪 **Guruhga qo'shilganlar:** {stats['group_joins_count']} ta\n"
        f"🔗 **Do'stlar taklifi orqali:** {stats['referred_joins_count']} ta\n\n"
        "Quyidagi tugmalar orqali batafsil ko'rishingiz mumkin:"
    )
    await message.answer(text, reply_markup=get_admin_panel_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_refresh")
async def cb_admin_refresh(callback: CallbackQuery):
    admin_id = await get_effective_admin_chat_id()
    if not admin_id or callback.from_user.id != admin_id:
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    stats = await get_stats()
    text = (
        "📊 **Fermerlar Klubi — CustDev & Referrals Admin Panel**\n\n"
        f"👥 **Jami anketalar:** {stats['total']} ta\n"
        f"🐄 **Chorvachilik:** {stats['chorva']} ta\n"
        f"🐔 **Parrandachilik:** {stats['parranda']} ta\n"
        f"📱 **Telefon qoldirganlar:** {stats['with_phone']} ta\n"
        f"🎙 **Ovozli xabar qoldirganlar:** {stats['with_voice']} ta\n"
        f"🚪 **Guruhga qo'shilganlar:** {stats['group_joins_count']} ta\n"
        f"🔗 **Do'stlar taklifi orqali:** {stats['referred_joins_count']} ta\n\n"
        "Quyidagi tugmalar orqali batafsil ko'rishingiz mumkin:"
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_admin_panel_keyboard(), parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer("Yangilandi!")

@router.callback_query(F.data == "admin_refresh_stats")
async def cb_admin_refresh_stats(callback: CallbackQuery):
    admin_id = await get_effective_admin_chat_id()
    if not admin_id or str(callback.from_user.id) != str(admin_id):
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    stats = await get_stats()
    group_id = await get_effective_group_id()
    group_status = f"`{group_id}`" if group_id else "*Hali belgilanmagan*"
    
    admin_text = (
        "👑 **Administrator Boshqaruv Paneli**\n\n"
        f"📊 **Yangilangan statistika:**\n"
        f"• Jami anketalar: **{stats['total']} ta**\n"
        f"• Guruhga qo'shilganlar: **{stats['group_joins_count']} ta**\n"
        f"• Telefon qoldirganlar: **{stats['with_phone']} ta**\n"
        f"• Ovozli xabarlar: **{stats['with_voice']} ta**\n\n"
        f"📌 **Ulangan guruh ID:** {group_status}\n"
        f"🕒 *Oxirgi tekshiruv:* `{time.strftime('%H:%M:%S')}`"
    )
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Statistikani yangilash", callback_data="admin_refresh_stats")],
        [InlineKeyboardButton(text="👥 Taklif havolasini olish", callback_data="btn_invite_friends")]
    ])
    try:
        await callback.message.edit_text(admin_text, reply_markup=admin_kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer("Statistika yangilandi! ✅")

@router.callback_query(F.data == "admin_referrals_stats")
async def cb_admin_referrals_stats(callback: CallbackQuery):
    admin_id = await get_effective_admin_chat_id()
    if not admin_id or callback.from_user.id != admin_id:
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    top_ref = await get_top_referrers(limit=5)
    recent_joins = await get_group_joins(limit=5)
    stats = await get_stats()

    text_parts = [
        "👥 **Guruhga a'zo bo'lganlar & Do'stlar taklifi:**\n",
        f"• Guruhga kirganlar: **{stats['group_joins_count']} ta**",
        f"• Taklif orqali kirganlar: **{stats['referred_joins_count']} ta**\n",
        "🏆 **Eng ko'p do'st taklif qilganlar:**"
    ]
    if top_ref:
        for idx, tr in enumerate(top_ref, 1):
            u_text = f"@{tr['username']}" if tr['username'] else tr['full_name']
            text_parts.append(f"{idx}. {u_text} — **{tr['referral_count']} ta**")
    else:
        text_parts.append("Hozircha faol taklifchilar yo'q.")

    text_parts.append("\n🚪 **Oxirgi qo'shilganlar:**")
    if recent_joins:
        for j in recent_joins[:5]:
            ref_info = f" (Taklif: {j['inviter_name']})" if j.get('inviter_name') else ""
            text_parts.append(f"• {j['full_name']}{ref_info} — {j['joined_at'][:16]}")
    else:
        text_parts.append("Hali hech kim qo'shilmadi.")

    text_parts.append("\n🌐 Veb admin panel: `http://localhost:8080/members`")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="admin_refresh")]
    ])
    await callback.message.edit_text("\n".join(text_parts), reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "admin_custdev_insights")
async def cb_admin_custdev_insights(callback: CallbackQuery):
    admin_id = await get_effective_admin_chat_id()
    if not admin_id or callback.from_user.id != admin_id:
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    rows = await get_all_responses()
    analytics = analyze_custdev(rows)
    stats = await get_stats()

    if stats["total"] == 0:
        await callback.answer("Hozircha anketalar mavjud emas!", show_alert=True)
        return

    text_parts = ["🔍 **CustDev Tahlili — Eng ko'p muammolar:**\n"]
    for cat in analytics["categories"]:
        if cat["count"] > 0:
            text_parts.append(f"• **{cat['title']}**: {cat['percentage']}% ({cat['count']} ta)")

    text_parts.append("\n👥 **Kimlarda bu ko'proq uchrayapti?**")
    cross = analytics["cross_table"]
    for seg_name, count in analytics["segment_counts"].items():
        if count > 0:
            top_prob = "Aniqlanmagan"
            if seg_name in cross:
                sorted_probs = sorted(cross[seg_name].items(), key=lambda x: x[1], reverse=True)
                if sorted_probs and sorted_probs[0][1] > 0:
                    top_key = sorted_probs[0][0]
                    top_prob = CATEGORIES[top_key]["title"]
            text_parts.append(f"📌 **{seg_name}** ({count} ta):\n   Asosiy dard: _{top_prob}_")

    text_parts.append("\n🌐 Batafsil grafik va ro'yxat: `http://localhost:8080/analysis`")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="admin_refresh")]
    ])

    await callback.message.edit_text("\n".join(text_parts), reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "admin_download_csv")
async def cb_admin_download_csv(callback: CallbackQuery, bot: Bot):
    admin_id = await get_effective_admin_chat_id()
    if not admin_id or callback.from_user.id != admin_id:
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    await callback.answer("CSV fayl tayyorlanmoqda...")
    export_to_csv()
    if os.path.exists(OUTPUT_CSV):
        await bot.send_document(
            chat_id=callback.from_user.id,
            document=FSInputFile(OUTPUT_CSV),
            caption="📊 **CustDev javoblari (Excel / CSV formati)**",
            parse_mode="Markdown"
        )
    else:
        await callback.message.answer("Hozircha bazada hech qanday ma'lumot yo'q.")

@router.callback_query(F.data.startswith("admin_recent_"))
async def cb_admin_recent(callback: CallbackQuery):
    admin_id = await get_effective_admin_chat_id()
    if not admin_id or callback.from_user.id != admin_id:
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    offset = int(callback.data.split("_")[2])
    limit = 3
    responses = await get_recent_responses(limit=limit, offset=offset)
    stats = await get_stats()
    total = stats["total"]

    if not responses:
        await callback.answer("Boshqa javoblar yo'q!", show_alert=True)
        return

    text_parts = [f"📋 **Oxirgi CustDev javoblari** (Jami: {total} ta):\n"]
    for idx, r in enumerate(responses, start=offset + 1):
        direction_badge = "🐄 Chorva" if r["direction"] == "chorva" else "🐔 Parranda"
        phone = r["phone_number"] or "Qoldirilmagan"
        username = f"@{r['username']}" if r["username"] else "yo'q"
        ref_text = f" (Taklif: {r['referrer_name']})" if r.get('referrer_name') else ""
        text_parts.append(
            f"**#{idx} — {r['full_name']}** ({username} | ID: `{r['user_id']}`){ref_text}\n"
            f"🏷 {direction_badge} (Hajm: {r['livestock_count']})\n"
            f"📞 Telefon: `{phone}`\n"
            f"📌 **Muammo (2):** {r['problem']}\n"
            f"🛠 **Yechim (3):** {r['solution_taken']}\n"
            f"❓ **Yetishmagan (4):** {r['dissatisfaction']}\n"
            "──────────────────"
        )

    nav_buttons = []
    if offset > 0:
        prev_offset = max(0, offset - limit)
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"admin_recent_{prev_offset}"))
    if offset + limit < total:
        next_offset = offset + limit
        nav_buttons.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"admin_recent_{next_offset}"))

    kb_rows = []
    if nav_buttons:
        kb_rows.append(nav_buttons)
    kb_rows.append([InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="admin_refresh")])

    await callback.message.edit_text(
        "\n".join(text_parts),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
        parse_mode="Markdown"
    )
    await callback.answer()

# ==================== KUTILMAGAN XABARLAR / OVOZLI XABARLAR ====================

@router.message(F.voice | F.audio)
async def handle_unexpected_voice(message: Message, state: FSMContext):
    """Anketa to'ldirish bosqichida bo'lmagan foydalanuvchi ovozli xabar yuborsa"""
    curr = await state.get_state()
    if not curr:
        await message.answer(
            "Assalomu alaykum! 🌾 Fermerlar Klubiga a'zo bo'lish uchun /start buyrug'ini bosing.",
            parse_mode="Markdown"
        )
