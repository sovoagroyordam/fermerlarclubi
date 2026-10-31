import os
import logging
import hashlib
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import aiosqlite

logger = logging.getLogger(__name__)

DB_NAME = os.getenv("DB_PATH", "fermamax.db")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

_pg_pool = None
_pg_disabled = False

def is_postgres() -> bool:
    return bool(DATABASE_URL) and not _pg_disabled

def _clean_row(row) -> dict:
    if row is None:
        return None
    d = dict(row)
    for k, v in d.items():
        if hasattr(v, "strftime"):
            d[k] = v.strftime("%Y-%m-%d %H:%M:%S")
    return d

async def get_pg_pool():
    global _pg_pool, _pg_disabled
    if _pg_disabled:
        return None
    if _pg_pool is None:
        import asyncpg
        dsn = DATABASE_URL
        if dsn.startswith("postgres://"):
            dsn = "postgresql://" + dsn[11:]
        
        ssl_mode = None
        if "sslmode=require" in dsn or "neon.tech" in dsn or "supabase" in dsn:
            try:
                u = urlparse(dsn)
                query_params = parse_qs(u.query)
                query_params.pop("sslmode", None)
                new_query = urlencode(query_params, doseq=True)
                dsn = urlunparse((u.scheme, u.netloc, u.path, u.params, new_query, u.fragment))
                ssl_mode = "require"
            except Exception as e:
                logger.warning(f"DSN parse xatosi: {e}")
                ssl_mode = "require"

        logger.info("🐘 PostgreSQL (Neon) bazasiga ulanmoqda...")
        try:
            _pg_pool = await asyncpg.create_pool(dsn, ssl=ssl_mode, min_size=1, max_size=10, timeout=10)
            logger.info("✅ PostgreSQL (Neon) ulanishi muvaffaqiyatli o'rnatildi!")
        except Exception as e:
            logger.warning(f"⚠️ SSL='require' bilan ulanish o'xshamadi ({e}), ssl=True bilan urinib ko'ramiz...")
            try:
                _pg_pool = await asyncpg.create_pool(dsn, ssl=True, min_size=1, max_size=10, timeout=10)
                logger.info("✅ PostgreSQL (Neon) ulanishi (ssl=True) o'rnatildi!")
            except Exception as e2:
                logger.error(f"❌ PostgreSQL ga ulanishda xatolik: {e2}. SQLite bazasiga o'tilmoqda!")
                _pg_disabled = True
                return None
    return _pg_pool

def _format_sql(sql: str) -> str:
    if not is_postgres():
        return sql
    # ? belgilarini $1, $2, ... ga o'zgartirish
    parts = sql.split("?")
    if len(parts) > 1:
        new_parts = []
        for i, part in enumerate(parts[:-1]):
            new_parts.append(part)
            new_parts.append(f"${i+1}")
        new_parts.append(parts[-1])
        sql = "".join(new_parts)
    
    # SQLite va PostgreSQL farqlarini moslashtirish
    sql = sql.replace("datetime('now', '-60 seconds')", "NOW() - INTERVAL '60 seconds'")
    return sql

async def db_execute(sql: str, params: tuple = ()):
    if is_postgres():
        pool = await get_pg_pool()
        if pool:
            sql_fmt = _format_sql(sql)
            try:
                async with pool.acquire() as conn:
                    await conn.execute(sql_fmt, *params)
                return
            except Exception as e:
                logger.error(f"PostgreSQL execute xatosi: {e}")
    # SQLite fallback
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(sql, params)
        await db.commit()

async def db_fetch_one(sql: str, params: tuple = ()) -> dict:
    if is_postgres():
        pool = await get_pg_pool()
        if pool:
            sql_fmt = _format_sql(sql)
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(sql_fmt, *params)
                    return _clean_row(row)
            except Exception as e:
                logger.error(f"PostgreSQL fetchrow xatosi: {e}")
    # SQLite fallback
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cur:
            row = await cur.fetchone()
            return _clean_row(row)

async def db_fetch_val(sql: str, params: tuple = ()):
    if is_postgres():
        pool = await get_pg_pool()
        if pool:
            sql_fmt = _format_sql(sql)
            try:
                async with pool.acquire() as conn:
                    return await conn.fetchval(sql_fmt, *params)
            except Exception as e:
                logger.error(f"PostgreSQL fetchval xatosi: {e}")
    # SQLite fallback
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(sql, params) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def db_fetch_all(sql: str, params: tuple = ()) -> list:
    if is_postgres():
        pool = await get_pg_pool()
        if pool:
            sql_fmt = _format_sql(sql)
            try:
                async with pool.acquire() as conn:
                    rows = await conn.fetch(sql_fmt, *params)
                    return [_clean_row(r) for r in rows]
            except Exception as e:
                logger.error(f"PostgreSQL fetchall xatosi: {e}")
    # SQLite fallback
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [_clean_row(r) for r in rows]

# ==================== JADVALLARNI YARATISH (INIT) ====================

async def init_db():
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT UNIQUE,
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
                    referred_by BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS invite_links (
                    id SERIAL PRIMARY KEY,
                    link TEXT UNIQUE,
                    creator_user_id BIGINT,
                    invite_type TEXT DEFAULT 'custdev_complete',
                    used_by_user_id BIGINT,
                    used_by_name TEXT,
                    is_used INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    used_at TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS group_joins (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    full_name TEXT,
                    username TEXT,
                    invited_by BIGINT,
                    invite_link TEXT,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS referral_codes (
                    user_id BIGINT PRIMARY KEY,
                    code TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        logger.info("🐘 PostgreSQL (Neon) jadvallari tayyorlandi.")
    else:
        dirname = os.path.dirname(os.path.abspath(DB_NAME))
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        async with aiosqlite.connect(DB_NAME) as db:
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
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
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
            await db.execute("""
                CREATE TABLE IF NOT EXISTS referral_codes (
                    user_id INTEGER PRIMARY KEY,
                    code TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()
        logger.info("📁 Mahalliy SQLite bazasi (fermamax.db) tayyorlandi.")

# ==================== MAXFIY REFERRAL KODLARI (USER ID MAXFIY) ====================

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
    row = await db_fetch_one("SELECT code FROM referral_codes WHERE user_id = ?", (user_id,))
    if row:
        return row["code"]

    code = generate_secret_code(user_id)
    await db_execute("""
        INSERT INTO referral_codes (user_id, code)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET code = EXCLUDED.code
    """, (user_id, code))
    return code

async def resolve_referral_code(code: str):
    if not code:
        return None
    clean = code.strip()
    if clean.startswith("ref_"):
        clean = clean[4:]
    
    row = await db_fetch_one("SELECT user_id FROM referral_codes WHERE code = ?", (clean,))
    if row:
        return row["user_id"]
    
    row = await db_fetch_one("SELECT user_id FROM referral_codes WHERE code = ?", (f"c_{clean}",))
    if row:
        return row["user_id"]
    
    if clean.isdigit():
        return int(clean)
    return None

# ==================== SOZLAMALAR ====================

async def set_setting(key: str, value: str):
    await db_execute("""
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value
    """, (key, str(value)))

async def get_setting(key: str, default=None):
    val = await db_fetch_val("SELECT value FROM settings WHERE key = ?", (key,))
    return val if val is not None else default

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
    await db_execute("""
        INSERT INTO responses (
            user_id, full_name, username, direction, livestock_count,
            problem, problem_voice_id, problem_voice_path,
            solution_taken, solution_voice_id, solution_voice_path,
            dissatisfaction, dissatisfaction_voice_id, dissatisfaction_voice_path,
            phone_number, referred_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            full_name = EXCLUDED.full_name,
            username = EXCLUDED.username,
            direction = EXCLUDED.direction,
            livestock_count = EXCLUDED.livestock_count,
            problem = EXCLUDED.problem,
            problem_voice_id = EXCLUDED.problem_voice_id,
            problem_voice_path = CASE 
                WHEN EXCLUDED.problem_voice_path != '' THEN EXCLUDED.problem_voice_path
                ELSE responses.problem_voice_path
            END,
            solution_taken = EXCLUDED.solution_taken,
            solution_voice_id = EXCLUDED.solution_voice_id,
            solution_voice_path = CASE 
                WHEN EXCLUDED.solution_voice_path != '' THEN EXCLUDED.solution_voice_path
                ELSE responses.solution_voice_path
            END,
            dissatisfaction = EXCLUDED.dissatisfaction,
            dissatisfaction_voice_id = EXCLUDED.dissatisfaction_voice_id,
            dissatisfaction_voice_path = CASE 
                WHEN EXCLUDED.dissatisfaction_voice_path != '' THEN EXCLUDED.dissatisfaction_voice_path
                ELSE responses.dissatisfaction_voice_path
            END,
            phone_number = CASE 
                WHEN EXCLUDED.phone_number != '' THEN EXCLUDED.phone_number 
                ELSE responses.phone_number 
            END,
            referred_by = CASE
                WHEN responses.referred_by IS NOT NULL THEN responses.referred_by
                ELSE EXCLUDED.referred_by
            END,
            created_at = CURRENT_TIMESTAMP
    """, (
        user_id, full_name, username, direction, livestock_count,
        problem, problem_voice_id, problem_voice_path,
        solution_taken, solution_voice_id, solution_voice_path,
        dissatisfaction, dissatisfaction_voice_id, dissatisfaction_voice_path,
        phone_number, referred_by
    ))

async def update_phone_number(user_id: int, phone_number: str):
    await db_execute("UPDATE responses SET phone_number = ? WHERE user_id = ?", (phone_number, user_id))

async def get_response(user_id: int):
    return await db_fetch_one("SELECT * FROM responses WHERE user_id = ?", (user_id,))

async def get_user_by_id(user_id: int):
    return await get_response(user_id)

# ==================== BIR MARTALIK TAKLIF HAVOLALARI ====================

async def save_invite_link(link: str, creator_user_id: int, invite_type: str = "custdev_complete"):
    await db_execute("""
        INSERT INTO invite_links (link, creator_user_id, invite_type)
        VALUES (?, ?, ?)
        ON CONFLICT(link) DO NOTHING
    """, (link, creator_user_id, invite_type))

async def get_invite_link(link: str):
    return await db_fetch_one("SELECT * FROM invite_links WHERE link = ?", (link,))

async def mark_invite_link_used(link: str, used_by_user_id: int, used_by_name: str = ""):
    await db_execute("""
        UPDATE invite_links 
        SET is_used = 1, used_by_user_id = ?, used_by_name = ?, used_at = CURRENT_TIMESTAMP
        WHERE link = ?
    """, (used_by_user_id, used_by_name, link))

# ==================== GURUHGA QO'SHILGANLARNI QAYD ETISH ====================

async def record_group_join(user_id: int, full_name: str, username: str = "", invited_by: int = None, invite_link: str = None) -> bool:
    """
    Guruhga qo'shilgan a'zoni qayd etish.
    UNIKAL USER ALGORITMI:
    Agar bu user_id avval guruhga qo'shilgan bo'lsa (qayta kirsa ham), yangi a'zo deb hisoblanmaydi (False qaytaradi).
    Faqat birinchi marta qo'shilayotgan yangi unikal a'zolar bazaga kiritiladi va True qaytaradi.
    """
    existing = await db_fetch_one("SELECT id, invited_by FROM group_joins WHERE user_id = ?", (user_id,))
    if existing:
        if invited_by and not existing.get("invited_by"):
            await db_execute("UPDATE group_joins SET invited_by = ?, invite_link = ? WHERE id = ?", (invited_by, invite_link, existing["id"]))
        return False  # Takroriy qo'shilish, yangi unikal a'zo emas

    await db_execute("""
        INSERT INTO group_joins (user_id, full_name, username, invited_by, invite_link)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, full_name, username, invited_by, invite_link))
    return True  # Yangi unikal a'zo!

async def get_group_joins(limit: int = 100):
    return await db_fetch_all("""
        SELECT j.id, j.user_id, j.full_name, j.username, j.invited_by, j.invite_link, j.joined_at,
               r.full_name AS inviter_name, r.username AS inviter_username
        FROM group_joins j
        LEFT JOIN responses r ON j.invited_by = r.user_id
        ORDER BY j.joined_at DESC
        LIMIT ?
    """, (limit,))

# ==================== REFERRALLAR (DO'STLAR TAKLIFI) ====================

async def get_user_referrals(user_id: int):
    return await db_fetch_all("""
        SELECT user_id, full_name, username, direction, created_at
        FROM responses
        WHERE referred_by = ?
        ORDER BY created_at DESC
    """, (user_id,))

async def get_user_referral_count(user_id: int) -> int:
    # Faqat unikal foydalanuvchilar soni
    c1 = await db_fetch_val("SELECT COUNT(DISTINCT user_id) FROM responses WHERE referred_by = ?", (user_id,)) or 0
    c2 = await db_fetch_val("SELECT COUNT(DISTINCT user_id) FROM group_joins WHERE invited_by = ?", (user_id,)) or 0
    return max(int(c1), int(c2))

async def get_top_referrers(limit: int = 10):
    # Har bir taklif qiluvchi uchun unikal a'zolar sanaladi
    return await db_fetch_all("""
        SELECT r.user_id, r.full_name, r.username, COUNT(DISTINCT j.user_id) AS referral_count
        FROM responses r
        JOIN group_joins j ON j.invited_by = r.user_id
        GROUP BY r.user_id, r.full_name, r.username
        ORDER BY referral_count DESC
        LIMIT ?
    """, (limit,))

# ==================== STATISTIKA VA RO'YXATLAR ====================

async def get_stats():
    total = await db_fetch_val("SELECT COUNT(*) FROM responses") or 0
    chorva = await db_fetch_val("SELECT COUNT(*) FROM responses WHERE direction = 'chorva'") or 0
    parranda = await db_fetch_val("SELECT COUNT(*) FROM responses WHERE direction = 'parranda'") or 0
    with_phone = await db_fetch_val("SELECT COUNT(*) FROM responses WHERE phone_number IS NOT NULL AND phone_number != ''") or 0
    with_voice = await db_fetch_val("""
        SELECT COUNT(*) FROM responses 
        WHERE (problem_voice_path IS NOT NULL AND problem_voice_path != '')
           OR (problem_voice_id IS NOT NULL AND problem_voice_id != '')
           OR (solution_voice_path IS NOT NULL AND solution_voice_path != '')
           OR (dissatisfaction_voice_path IS NOT NULL AND dissatisfaction_voice_path != '')
    """) or 0
    # UNIKAL USER_ID ALGORITMI: 10 ta qatordan 5 tasi 1 xil user bo'lsa, natija 6 ta chiqadi
    group_joins_count = await db_fetch_val("SELECT COUNT(DISTINCT user_id) FROM group_joins") or 0
    referred_joins_count = await db_fetch_val("SELECT COUNT(DISTINCT user_id) FROM group_joins WHERE invited_by IS NOT NULL") or 0

    return {
        "total": int(total),
        "chorva": int(chorva),
        "parranda": int(parranda),
        "with_phone": int(with_phone),
        "with_voice": int(with_voice),
        "group_joins_count": int(group_joins_count),
        "referred_joins_count": int(referred_joins_count),
    }

async def get_all_responses():
    return await db_fetch_all("""
        SELECT r.id, r.user_id, r.full_name, r.username, r.direction, r.livestock_count, 
               r.problem, r.problem_voice_id, r.problem_voice_path,
               r.solution_taken, r.solution_voice_id, r.solution_voice_path,
               r.dissatisfaction, r.dissatisfaction_voice_id, r.dissatisfaction_voice_path,
               r.phone_number, r.referred_by, r.created_at,
               ref.full_name AS referrer_name, ref.username AS referrer_username
        FROM responses r
        LEFT JOIN responses ref ON r.referred_by = ref.user_id
        ORDER BY r.created_at DESC
    """)

async def get_recent_responses(limit: int = 10, offset: int = 0):
    return await db_fetch_all("""
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
    """, (limit, offset))
