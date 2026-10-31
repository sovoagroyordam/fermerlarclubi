import os
import aiosqlite

DB_NAME = os.getenv("DB_PATH", "fermamax.db")

async def init_db():
    dirname = os.path.dirname(os.path.abspath(DB_NAME))
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    async with aiosqlite.connect(DB_NAME) as db:
        # 1. Responses jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                full_name TEXT,
                username TEXT,
                direction TEXT,
                livestock_count TEXT,
                problem TEXT,
                problem_voice_id TEXT,
                problem_voice_path TEXT,
                solution_taken TEXT,
                solution_voice_id TEXT,
                solution_voice_path TEXT,
                dissatisfaction TEXT,
                dissatisfaction_voice_id TEXT,
                dissatisfaction_voice_path TEXT,
                phone_number TEXT,
                referred_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Eski bazaga yangi ustunlar qo'shish
        columns_to_add = [
            ("phone_number", "TEXT"),
            ("problem_voice_path", "TEXT"),
            ("solution_voice_path", "TEXT"),
            ("dissatisfaction_voice_path", "TEXT"),
            ("referred_by", "INTEGER"),
        ]
        for col_name, col_type in columns_to_add:
            try:
                await db.execute(f"ALTER TABLE responses ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

        # 2. Sozlamalar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # 3. Bir martalik taklif havolalari (Invite links)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invite_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT UNIQUE,
                creator_user_id INTEGER,
                invite_type TEXT DEFAULT 'custdev_complete',
                used_by_user_id INTEGER,
                used_by_name TEXT,
                is_used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_at TIMESTAMP
            )
        """)

        # 4. Guruhga qo'shilganlar jurnali (Group joins tracking)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS group_joins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                full_name TEXT,
                username TEXT,
                invited_by INTEGER,
                invite_link TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 5. Maxfiy referral kodlari (User ID ni yashirish uchun)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referral_codes (
                user_id INTEGER PRIMARY KEY,
                code TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()

# ==================== MAXFIY REFERRAL KODLARI (USER ID MAXFIY) ====================

import hashlib

def mask_user_id(user_id: int) -> str:
    """Telegram chat/user ID ni maxfiylashtirish (masalan: ***3772)"""
    if not user_id:
        return "—"
    s = str(user_id)
    if len(s) > 4:
        return f"***{s[-4:]}"
    return f"***{s}"

def generate_secret_code(user_id: int) -> str:
    secret = os.getenv("SECRET_KEY", "fermamax_secret_salt_2026")
    h = hashlib.sha256(f"{user_id}_{secret}".encode()).hexdigest()[:8]
    return f"c_{h}"

async def get_or_create_referral_code(user_id: int) -> str:
    """Foydalanuvchi ID sini ochiqlamaydigan maxfiy 8 belgili token yaratish yoki olish"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT code FROM referral_codes WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return row[0]

        code = generate_secret_code(user_id)
        await db.execute("""
            INSERT INTO referral_codes (user_id, code)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET code = excluded.code
        """, (user_id, code))
        await db.commit()
        return code

async def resolve_referral_code(code: str):
    """Maxfiy token orqali taklif qilgan fermer user_id sini topish"""
    if not code:
        return None
    clean = code.strip()
    if clean.startswith("ref_"):
        clean = clean[4:]
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM referral_codes WHERE code = ?", (clean,)) as cur:
            row = await cur.fetchone()
            if row:
                return row[0]
        async with db.execute("SELECT user_id FROM referral_codes WHERE code = ?", (f"c_{clean}",)) as cur:
            row = await cur.fetchone()
            if row:
                return row[0]
        # Agar eski raqamli ID bilan kelgan bo'lsa (backward compatibility)
        if clean.isdigit():
            return int(clean)
    return None

# ==================== SOZLAMALAR ====================

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, str(value)))
        await db.commit()

async def get_setting(key: str, default=None):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            return default

# ==================== ANKETA JAVOBLARI ====================

async def save_response(
    user_id: int,
    full_name: str,
    username: str,
    direction: str,
    livestock_count: str,
    problem: str,
    problem_voice_id: str = "",
    problem_voice_path: str = "",
    solution_taken: str = "",
    solution_voice_id: str = "",
    solution_voice_path: str = "",
    dissatisfaction: str = "",
    dissatisfaction_voice_id: str = "",
    dissatisfaction_voice_path: str = "",
    phone_number: str = "",
    referred_by: int = None,
):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO responses (
                user_id, full_name, username, direction, livestock_count,
                problem, problem_voice_id, problem_voice_path,
                solution_taken, solution_voice_id, solution_voice_path,
                dissatisfaction, dissatisfaction_voice_id, dissatisfaction_voice_path,
                phone_number, referred_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name,
                username = excluded.username,
                direction = excluded.direction,
                livestock_count = excluded.livestock_count,
                problem = excluded.problem,
                problem_voice_id = excluded.problem_voice_id,
                problem_voice_path = CASE 
                    WHEN excluded.problem_voice_path != '' THEN excluded.problem_voice_path
                    ELSE responses.problem_voice_path
                END,
                solution_taken = excluded.solution_taken,
                solution_voice_id = excluded.solution_voice_id,
                solution_voice_path = CASE 
                    WHEN excluded.solution_voice_path != '' THEN excluded.solution_voice_path
                    ELSE responses.solution_voice_path
                END,
                dissatisfaction = excluded.dissatisfaction,
                dissatisfaction_voice_id = excluded.dissatisfaction_voice_id,
                dissatisfaction_voice_path = CASE 
                    WHEN excluded.dissatisfaction_voice_path != '' THEN excluded.dissatisfaction_voice_path
                    ELSE responses.dissatisfaction_voice_path
                END,
                phone_number = CASE 
                    WHEN excluded.phone_number != '' THEN excluded.phone_number 
                    ELSE responses.phone_number 
                END,
                referred_by = CASE
                    WHEN responses.referred_by IS NOT NULL THEN responses.referred_by
                    ELSE excluded.referred_by
                END,
                created_at = CURRENT_TIMESTAMP
        """, (
            user_id, full_name, username, direction, livestock_count,
            problem, problem_voice_id, problem_voice_path,
            solution_taken, solution_voice_id, solution_voice_path,
            dissatisfaction, dissatisfaction_voice_id, dissatisfaction_voice_path,
            phone_number, referred_by
        ))
        await db.commit()

async def update_phone_number(user_id: int, phone_number: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE responses SET phone_number = ? WHERE user_id = ?", (phone_number, user_id))
        await db.commit()

async def get_response(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM responses WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_user_by_id(user_id: int):
    return await get_response(user_id)

# ==================== BIR MARTALIK TAKLIF HAVOLALARI ====================

async def save_invite_link(link: str, creator_user_id: int, invite_type: str = "custdev_complete"):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            INSERT INTO invite_links (link, creator_user_id, invite_type)
            VALUES (?, ?, ?)
            ON CONFLICT(link) DO NOTHING
        """, (link, creator_user_id, invite_type))
        await db.commit()

async def get_invite_link(link: str):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM invite_links WHERE link = ?", (link,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def mark_invite_link_used(link: str, used_by_user_id: int, used_by_name: str = ""):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE invite_links 
            SET is_used = 1, used_by_user_id = ?, used_by_name = ?, used_at = CURRENT_TIMESTAMP
            WHERE link = ?
        """, (used_by_user_id, used_by_name, link))
        await db.commit()

# ==================== GURUHGA QO'SHILGANLARNI QAYD ETISH ====================

async def record_group_join(user_id: int, full_name: str, username: str = "", invited_by: int = None, invite_link: str = None):
    async with aiosqlite.connect(DB_NAME) as db:
        # Oxirgi 60 soniyada xuddi shu foydalanuvchi qayd etilgan bo'lsa takrorlamaslik
        async with db.execute(
            "SELECT id FROM group_joins WHERE user_id = ? AND joined_at >= datetime('now', '-60 seconds')",
            (user_id,)
        ) as cur:
            existing = await cur.fetchone()
            if existing:
                return

        await db.execute("""
            INSERT INTO group_joins (user_id, full_name, username, invited_by, invite_link)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, full_name, username, invited_by, invite_link))
        await db.commit()

async def get_group_joins(limit: int = 100):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT j.id, j.user_id, j.full_name, j.username, j.invited_by, j.invite_link, j.joined_at,
                   r.full_name AS inviter_name, r.username AS inviter_username
            FROM group_joins j
            LEFT JOIN responses r ON j.invited_by = r.user_id
            ORDER BY j.joined_at DESC
            LIMIT ?
        """, (limit,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

# ==================== REFERRALLAR (DO'STLAR TAKLIFI) ====================

async def get_user_referrals(user_id: int):
    """Foydalanuvchi taklif qilgan va qo'shilgan/anketa to'ldirgan do'stlari ro'yxati"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, full_name, username, direction, created_at
            FROM responses
            WHERE referred_by = ?
            ORDER BY created_at DESC
        """, (user_id,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_user_referral_count(user_id: int) -> int:
    """Foydalanuvchi nechta do'stini olib kelgan"""
    async with aiosqlite.connect(DB_NAME) as db:
        # 1. responses orqali
        async with db.execute("SELECT COUNT(*) FROM responses WHERE referred_by = ?", (user_id,)) as cur:
            c1 = (await cur.fetchone())[0]
        # 2. group_joins orqali
        async with db.execute("SELECT COUNT(*) FROM group_joins WHERE invited_by = ?", (user_id,)) as cur:
            c2 = (await cur.fetchone())[0]
        return max(c1, c2)

async def get_top_referrers(limit: int = 10):
    """Eng ko'p do'st taklif qilgan fermerlar reytingi"""
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.user_id, r.full_name, r.username, COUNT(j.id) AS referral_count
            FROM responses r
            JOIN group_joins j ON j.invited_by = r.user_id
            GROUP BY r.user_id
            ORDER BY referral_count DESC
            LIMIT ?
        """, (limit,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

# ==================== STATISTIKA VA RO'YXATLAR ====================

async def get_stats():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM responses") as cur:
            total = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM responses WHERE direction = 'chorva'") as cur:
            chorva = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM responses WHERE direction = 'parranda'") as cur:
            parranda = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM responses WHERE phone_number IS NOT NULL AND phone_number != ''") as cur:
            with_phone = (await cur.fetchone())[0]
        async with db.execute("""
            SELECT COUNT(*) FROM responses 
            WHERE (problem_voice_path IS NOT NULL AND problem_voice_path != '')
               OR (problem_voice_id IS NOT NULL AND problem_voice_id != '')
               OR (solution_voice_path IS NOT NULL AND solution_voice_path != '')
               OR (dissatisfaction_voice_path IS NOT NULL AND dissatisfaction_voice_path != '')
        """) as cur:
            with_voice = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM group_joins") as cur:
            group_joins_count = (await cur.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM group_joins WHERE invited_by IS NOT NULL") as cur:
            referred_joins_count = (await cur.fetchone())[0]

        return {
            "total": total,
            "chorva": chorva,
            "parranda": parranda,
            "with_phone": with_phone,
            "with_voice": with_voice,
            "group_joins_count": group_joins_count,
            "referred_joins_count": referred_joins_count,
        }

async def get_all_responses():
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.id, r.user_id, r.full_name, r.username, r.direction, r.livestock_count, 
                   r.problem, r.problem_voice_id, r.problem_voice_path,
                   r.solution_taken, r.solution_voice_id, r.solution_voice_path,
                   r.dissatisfaction, r.dissatisfaction_voice_id, r.dissatisfaction_voice_path,
                   r.phone_number, r.referred_by, r.created_at,
                   ref.full_name AS referrer_name, ref.username AS referrer_username
            FROM responses r
            LEFT JOIN responses ref ON r.referred_by = ref.user_id
            ORDER BY r.created_at DESC
        """) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def get_recent_responses(limit: int = 10, offset: int = 0):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT r.id, r.user_id, r.full_name, r.username, r.direction, r.livestock_count, 
                   r.problem, r.problem_voice_id, r.problem_voice_path,
                   r.solution_taken, r.solution_voice_id, r.solution_voice_path,
                   r.dissatisfaction, r.dissatisfaction_voice_id, r.dissatisfaction_voice_path,
                   r.phone_number, r.referred_by, r.created_at,
                   ref.full_name AS referrer_name, ref.username AS referrer_username
            FROM responses r
            LEFT JOIN responses ref ON r.referred_by = ref.user_id
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
