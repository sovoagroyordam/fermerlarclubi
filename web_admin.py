import csv
import io
import os
import html as html_lib
import hmac
import hashlib
from aiohttp import web
from config import ADMIN_USERNAME, ADMIN_PASSWORD, SECRET_KEY, BOT_TOKEN
from database import (
    init_db, 
    get_stats, 
    get_all_responses, 
    get_group_joins, 
    get_top_referrers,
    get_user_referral_count,
    mask_user_id
)
from analytics import analyze_custdev, detect_category, CATEGORIES

VOICE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices")
os.makedirs(VOICE_DIR, exist_ok=True)

LOGO_PATH_D = (
    "M582.48,365.47c-41.25,168.68-220.15,268.62-389.51,207.08,17.79-26.22,35.7-51.29,52.31-79.24,"
    "8.83-14.85,15.71-37.24,33.78-42.39,24.08-6.88,44.93-13.73,68.64-22.89,25.88-9.99,76.83,9.75,"
    "98.08-9.59,14.02-12.76,23.58-36.94,24.08-55.14.47-17-18.13-20.47-29.52-24.76-11.91-4.48-20.72-14.99-"
    "29.85-23.91-13.27-12.97-29.68-26.41-35.46-43.94-4.56-13.84-9.84-21.76-20.38-31.15l-20.51-18.27"
    "c20.29-15.84,25.65-33.12,25.85-56.96l.34-41.11c-9.31,5.23-15.51,18.13-17.44,31.33-1.24,23.29-17.73,41.51-"
    "39.55,44.63-26.35-11.08-53.19-2.9-72.78,15.34-9.32.36-19.74-11.5-20.79-21.64-3.59-34.84,17.83-60-6.86-79.12-"
    ".47,16.53-5.64,30.95-15.9,42.49-21.82,24.54-23.02,56.65.46,80.24.81,2.39-9.16,9.19-11.68,6.88-15.37-15.71-"
    "43.39-29.86-66.01-19.72-3.69,1.66-7.24,11.94-6.05,15.73,1.38,4.43,7.51,12.28,12.18,13.81l39.73,13"
    "c-23.3,22.8-55.19,32.68-88,28.42L0,285.81C6.39,107.95,164.43-21.48,337.26,2.97c172.01,24.34,286.73,192.74,"
    "245.22,362.5Z"
)

def render_logo_svg(size=24, color="#000000"):
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 591 590.84" xmlns="http://www.w3.org/2000/svg" style="display:inline-block;vertical-align:middle;">'
        f'<path fill="{color}" d="{LOGO_PATH_D}"/>'
        f'</svg>'
    )

def safe_str(val, default="—") -> str:
    if val is None or val == "":
        return default
    return html_lib.escape(str(val))

def safe_datetime(val) -> str:
    if not val:
        return ""
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d %H:%M")
    s = str(val)
    return s[:16] if len(s) >= 16 else s

def generate_auth_token() -> str:
    msg = f"{ADMIN_USERNAME}:{ADMIN_PASSWORD}".encode("utf-8")
    return hmac.new(SECRET_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()

def is_authenticated(request: web.Request) -> bool:
    valid_token = generate_auth_token()
    # 1. URL token tekshiruvi (Telegram WebApp / Mini App orqali 1-klikda avto-login)
    token_in_query = request.query.get("token")
    if token_in_query and hmac.compare_digest(token_in_query, valid_token):
        return True
    
    # 2. Brauzer Cookie tekshiruvi
    cookie_token = request.cookies.get("gh_auth")
    if cookie_token and hmac.compare_digest(cookie_token, valid_token):
        return True
    return False

def render_html_response(request: web.Request, html: str) -> web.Response:
    resp = web.Response(text=html, content_type="text/html")
    # Agar URLda token bo'lsa, cookie ham o'rnatamiz (keyingi sahifalar /analysis, /members uchun)
    if request.query.get("token") and is_authenticated(request):
        resp.set_cookie("gh_auth", generate_auth_token(), max_age=86400 * 30, httponly=True)
    return resp

# ----------------- LOGIN HTML -----------------
LOGIN_HTML = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sign in to Fermamax</title>
    <link rel="icon" type="image/svg+xml" href="/logo.svg">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script>
        if (window.Telegram && window.Telegram.WebApp) {
            try { window.Telegram.WebApp.ready(); window.Telegram.WebApp.expand(); } catch(e) {}
        }
    </script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
            background-color: #f6f8fa;
            color: #1f2328;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 32px 16px;
        }
        .gh-logo { margin-bottom: 24px; text-align: center; }
        .login-title {
            font-size: 24px;
            font-weight: 300;
            letter-spacing: -0.5px;
            margin-bottom: 16px;
        }
        .login-box {
            width: 100%;
            max-width: 340px;
            background: #ffffff;
            border: 1px solid #d8dee4;
            border-radius: 6px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(31, 35, 40, 0.04);
        }
        .form-group { margin-bottom: 16px; }
        label { display: block; margin-bottom: 6px; font-size: 14px; font-weight: 500; }
        input[type="text"], input[type="password"] {
            width: 100%;
            padding: 6px 12px;
            font-size: 14px;
            line-height: 20px;
            color: #1f2328;
            background-color: #ffffff;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            outline: none;
            transition: 0.2s;
        }
        input[type="text"]:focus, input[type="password"]:focus {
            border-color: #0969da;
            box-shadow: 0 0 0 3px rgba(9, 105, 218, 0.3);
        }
        .btn-submit {
            width: 100%;
            margin-top: 16px;
            padding: 6px 16px;
            font-size: 14px;
            font-weight: 600;
            color: #ffffff;
            background-color: #1f883d;
            border: 1px solid rgba(31, 35, 40, 0.15);
            border-radius: 6px;
            cursor: pointer;
        }
        .btn-submit:hover { background-color: #1a7f37; }
        .error-alert {
            background-color: #ffebe9;
            color: #cf222e;
            border: 1px solid rgba(255, 129, 130, 0.4);
            border-radius: 6px;
            padding: 12px 16px;
            font-size: 13px;
            margin-bottom: 16px;
            width: 100%;
            max-width: 340px;
            text-align: center;
        }
        .footer-note { margin-top: 24px; font-size: 12px; color: #656d76; }
    </style>
</head>
<body>
    <div class="gh-logo">
        {{fermamax_logo_large}}
    </div>
    <div class="login-title">Sign in to Fermamax</div>
    {{error_block}}
    <div class="login-box">
        <form method="POST" action="/login">
            <div class="form-group">
                <label for="username">Username or email address</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="btn-submit">Sign in</button>
        </form>
    </div>
    <div class="footer-note">Fermamax CustDev Admin Panel</div>
</body>
</html>
"""

# ----------------- COMMON GITHUB STYLES & HEADER -----------------
COMMON_CSS = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
        background-color: #f6f8fa;
        color: #1f2328;
        font-size: 14px;
        line-height: 1.5;
    }
    .gh-header {
        background-color: #ffffff;
        border-bottom: 1px solid #d0d7de;
        padding: 12px 24px 0 24px;
    }
    .gh-header-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
    }
    .gh-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 16px;
    }
    .gh-brand a {
        color: #0969da;
        text-decoration: none;
        font-weight: 600;
    }
    .gh-badge {
        font-size: 12px;
        font-weight: 500;
        padding: 1px 7px;
        border-radius: 20px;
        border: 1px solid #d0d7de;
        color: #656d76;
    }
    .gh-actions {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .btn-gh-primary {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 12px;
        font-size: 13px;
        font-weight: 600;
        color: #ffffff;
        background-color: #1f883d;
        border: 1px solid rgba(31, 35, 40, 0.15);
        border-radius: 6px;
        cursor: pointer;
        text-decoration: none;
    }
    .btn-gh-primary:hover { background-color: #1a7f37; }
    .btn-gh-logout {
        font-size: 13px;
        color: #cf222e;
        text-decoration: none;
        padding: 5px 10px;
        border-radius: 6px;
        border: 1px solid #d0d7de;
        background: #ffffff;
    }
    .btn-gh-logout:hover { background: #ffebe9; }

    /* Repo Tabs */
    .gh-tabs {
        display: flex;
        gap: 8px;
        list-style: none;
        overflow-x: auto;
    }
    .gh-tab {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 14px;
        font-size: 14px;
        color: #1f2328;
        text-decoration: none;
        border-bottom: 2px solid transparent;
        font-weight: 500;
        white-space: nowrap;
    }
    .gh-tab:hover { color: #0969da; }
    .gh-tab.active {
        font-weight: 600;
        color: #1f2328;
        border-bottom-color: #fd8c73;
    }
    .gh-tab-badge {
        background-color: rgba(175, 184, 193, 0.2);
        color: #1f2328;
        font-size: 12px;
        padding: 1px 6px;
        border-radius: 10px;
    }

    .container {
        max-width: 1200px;
        margin: 20px auto;
        padding: 0 16px;
    }
    .Box {
        background-color: #ffffff;
        border: 1px solid #d0d7de;
        border-radius: 6px;
        overflow: hidden;
        margin-bottom: 20px;
    }
    .Box-header {
        background-color: #f6f8fa;
        border-bottom: 1px solid #d0d7de;
        padding: 12px 16px;
        font-size: 14px;
        font-weight: 600;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .Box-body { padding: 16px; }

    .gh-label { font-size: 11px; font-weight: 500; padding: 1px 7px; border-radius: 12px; border: 1px solid transparent; white-space: nowrap; }
    .label-chorva { background: #fff8c5; color: #9a6700; border-color: #d4a72c; }
    .label-parranda { background: #ddf4ff; color: #0969da; border-color: #54aeff; }
    .label-phone { background: #dafbe1; color: #1a7f37; border-color: #4ac26b; font-family: monospace; font-weight: 600; }
    .label-voice { background: #fbefff; color: #8250df; border-color: #d2a8ff; font-weight: 600; }
    .label-cat { background: #ffebe9; color: #cf222e; border-color: #ff8182; }
    .label-ref { background: #e0f2fe; color: #0284c7; border-color: #7dd3fc; }

    /* Audio Player Widget */
    .audio-player-box {
        margin-top: 6px;
        background: #f6f8fa;
        border: 1px solid #d0d7de;
        border-radius: 6px;
        padding: 8px 12px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .audio-player-box audio {
        height: 32px;
        flex: 1;
        max-width: 420px;
        outline: none;
    }

    @media (max-width: 768px) {
        .container { padding: 0 10px; margin: 12px auto; }
        .gh-header { padding: 10px 14px 0 14px; }
        .gh-header-top { flex-wrap: wrap; gap: 8px; }
        .gh-tabs { gap: 4px; padding-bottom: 4px; }
        .gh-tab { padding: 6px 10px; font-size: 13px; }
        .stats-bar { padding: 10px 12px; }
        .stats-items { gap: 10px; }
        .controls-bar { flex-direction: column; }
        .search-box { width: 100%; min-width: 100%; }
        .audio-player-box { flex-direction: column; align-items: stretch; gap: 8px; }
        .audio-player-box audio { width: 100%; max-width: 100%; }
        .issue-row { flex-direction: column; }
        .issue-summary { max-width: 100%; }
    }
"""

def render_navbar(active_repo: str, total_custdev: int, total_members: int, logo_small_svg: str) -> str:
    active_custdev = "active" if active_repo == "custdev" else ""
    active_analysis = "active" if active_repo == "analysis" else ""
    active_members = "active" if active_repo == "members" else ""

    return f"""
    <header class="gh-header">
        <div class="gh-header-top">
            <div class="gh-brand">
                {logo_small_svg}
                <a href="/">fermamax</a>
                <span style="color:#656d76;">/</span>
                <span style="font-weight:600;">{active_repo}</span>
                <span class="gh-badge">Public</span>
            </div>
            <div class="gh-actions">
                <a href="/download-csv" class="btn-gh-primary">
                    <svg height="14" viewBox="0 0 16 16" width="14" fill="#fff"><path d="M2.75 14A1.75 1.75 0 0 1 1 12.25v-2.5a.75.75 0 0 1 1.5 0v2.5c0 .138.112.25.25.25h10.5a.25.25 0 0 0 .25-.25v-2.5a.75.75 0 0 1 1.5 0v2.5A1.75 1.75 0 0 1 13.25 14Z"></path><path d="M7.25 7.689V2a.75.75 0 0 1 1.5 0v5.689l1.97-1.969a.749.749 0 1 1 1.06 1.06l-3.25 3.25a.749.749 0 0 1-1.06 0L4.22 6.78a.749.749 0 1 1 1.06-1.06l1.97 1.969Z"></path></svg>
                    Export CSV
                </a>
                <a href="/logout" class="btn-gh-logout">Sign out</a>
            </div>
        </div>
        <ul class="gh-tabs">
            <li>
                <a href="/" class="gh-tab {active_custdev}">
                    <svg height="16" viewBox="0 0 16 16" width="16" fill="currentColor"><path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"></path></svg>
                    custdev (javoblar)
                    <span class="gh-tab-badge">{total_custdev}</span>
                </a>
            </li>
            <li>
                <a href="/analysis" class="gh-tab {active_analysis}">
                    <svg height="16" viewBox="0 0 16 16" width="16" fill="currentColor"><path d="M1.5 1.75V13.5h13.75a.75.75 0 0 1 0 1.5H.75a.75.75 0 0 1-.75-.75V1.75a.75.75 0 0 1 1.5 0Zm14.28 2.53-5.25 5.25a.75.75 0 0 1-1.06 0L7 7.06 2.53 11.53a.75.75 0 0 1-1.06-1.06l5-5a.75.75 0 0 1 1.06 0L10 7.94l4.72-4.72a.75.75 0 0 1 1.06 1.06Z"></path></svg>
                    analysis (muammolar tahlili)
                </a>
            </li>
            <li>
                <a href="/members" class="gh-tab {active_members}">
                    <svg height="16" viewBox="0 0 16 16" width="16" fill="currentColor"><path d="M2 5.5a3.5 3.5 0 1 1 5.898 2.549 5.508 5.508 0 0 1 3.034 4.084.75.75 0 1 1-1.482.235 4.002 4.002 0 0 0-6.899 0 .75.75 0 0 1-1.482-.236A5.507 5.507 0 0 1 3.102 8.05 3.493 3.493 0 0 1 2 5.5ZM11 4a3.001 3.001 0 0 1 2.22 5.018 5.01 5.01 0 0 1 2.56 3.012.75.75 0 0 1-1.492.164 3.51 3.51 0 0 0-2.333-2.617.75.75 0 0 1-.418-.949A1.5 1.5 0 1 0 10.05 6.47a.75.75 0 0 1-.948.419.75.75 0 0 1-.419-.949A3.001 3.001 0 0 1 11 4Z"></path></svg>
                    members (guruh & takliflar)
                    <span class="gh-tab-badge">{total_members}</span>
                </a>
            </li>
        </ul>
    </header>
    """

# ----------------- REPO 1: CUSTDEV (RESPONSES LIST) -----------------
CUSTDEV_HTML = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>fermamax/custdev: Fermerlar Klubi</title>
    <link rel="icon" type="image/svg+xml" href="/logo.svg">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script>
        if (window.Telegram && window.Telegram.WebApp) {
            try { window.Telegram.WebApp.ready(); window.Telegram.WebApp.expand(); } catch(e) {}
        }
    </script>
    <style>
        """ + COMMON_CSS + """
        .stats-bar {
            background: #ffffff;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            padding: 12px 18px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 16px;
        }
        .stats-items { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
        .stat-item { font-size: 13px; color: #656d76; }
        .stat-item strong { font-size: 15px; color: #1f2328; font-weight: 600; }

        .controls-bar { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
        .search-box { flex: 1; min-width: 260px; position: relative; }
        .search-box svg { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); fill: #656d76; }
        .search-input {
            width: 100%;
            padding: 6px 12px 6px 32px;
            font-size: 14px;
            background-color: #ffffff;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            outline: none;
        }
        .search-input:focus { border-color: #0969da; box-shadow: 0 0 0 3px rgba(9, 105, 218, 0.2); }
        .filter-btn {
            padding: 5px 12px;
            font-size: 13px;
            font-weight: 500;
            color: #1f2328;
            background-color: #ffffff;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            cursor: pointer;
        }
        .filter-btn:hover { background-color: #f6f8fa; }
        .filter-btn.active { background-color: #0969da; color: #ffffff; border-color: #0969da; }

        .issue-row {
            border-bottom: 1px solid #d0d7de;
            padding: 12px 16px;
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }
        .issue-row:last-child { border-bottom: none; }
        .issue-row:hover { background-color: #f6f8fa; }
        .issue-icon { margin-top: 3px; fill: #1f883d; flex-shrink: 0; }
        .issue-content { flex: 1; min-width: 0; }
        .issue-header-line { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-bottom: 4px; }
        .issue-author { font-size: 14px; font-weight: 600; color: #1f2328; cursor: pointer; }
        .issue-author:hover { color: #0969da; }
        .issue-summary { font-size: 13px; color: #656d76; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 480px; }

        .issue-meta { font-size: 12px; color: #656d76; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
        .issue-details { display: none; margin-top: 10px; background: #ffffff; border: 1px solid #d0d7de; border-radius: 6px; padding: 12px 14px; font-size: 13px; }
        .issue-details.open { display: block; }
        .qa-block { margin-bottom: 12px; }
        .qa-block:last-child { margin-bottom: 0; }
        .qa-title { font-weight: 600; color: #1f2328; margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }
        .qa-text { color: #333; background: #f6f8fa; border: 1px solid #e1e4e8; border-radius: 4px; padding: 6px 10px; line-height: 1.4; }
        .empty-state { text-align: center; padding: 40px 16px; color: #656d76; }
    </style>
</head>
<body>
    {{navbar_placeholder}}

    <div class="container">
        <div class="stats-bar">
            <div class="stats-items">
                <div class="stat-item">Jami anketalar: <strong>{{total}}</strong></div>
                <div class="stat-item">🐄 Chorva: <strong>{{chorva}}</strong></div>
                <div class="stat-item">🐔 Parranda: <strong>{{parranda}}</strong></div>
                <div class="stat-item">📱 Telefonli: <strong style="color:#1a7f37;">{{with_phone}}</strong></div>
                <div class="stat-item">🎙 Ovozli javoblar: <strong style="color:#8250df;">{{with_voice}}</strong></div>
                <div class="stat-item">🚪 Guruhga kirganlar: <strong style="color:#0969da;">{{group_joins_count}}</strong></div>
            </div>
            <div>
                <button class="filter-btn" onclick="toggleAll()">Hamasini ochish / yopish</button>
            </div>
        </div>

        <div class="controls-bar">
            <div class="search-box">
                <svg height="14" viewBox="0 0 16 16" width="14"><path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.5 4.5 0 1 0-9 0 4.5 4.5 0 0 0 9 0Z"></path></svg>
                <input type="text" id="searchInput" class="search-input" placeholder="Qidiruv (ism, muammo, telefon, username)..." onkeyup="filterList()">
            </div>
            <button class="filter-btn active" onclick="setFilter('all', this)">Barchasi</button>
            <button class="filter-btn" onclick="setFilter('chorva', this)">🐄 Chorva</button>
            <button class="filter-btn" onclick="setFilter('parranda', this)">🐔 Parranda</button>
            <button class="filter-btn" onclick="setFilter('phone', this)">📞 Faqat telefonli</button>
            <button class="filter-btn" onclick="setFilter('voice', this)">🎙 Ovozli xabarli</button>
        </div>

        <div class="Box">
            <div class="Box-header">
                <div style="display:flex;align-items:center;gap:6px;">
                    <svg height="16" viewBox="0 0 16 16" width="16" fill="#1f883d"><path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"></path></svg>
                    <span id="displayCount">{{total}} ta anketalar</span>
                </div>
                <div style="font-size: 12px; color: #656d76; font-weight: normal;">
                    Fermer ismini bossangiz ovozli va yozma javoblar ochiladi
                </div>
            </div>
            <div id="issuesList">
                {{issue_items}}
            </div>
        </div>
    </div>

    <script>
        let currentCategory = 'all';
        function setFilter(cat, btn) {
            currentCategory = cat;
            document.querySelectorAll('.filter-btn').forEach(b => {
                if (b.innerText.includes('Hamasini')) return;
                b.classList.remove('active');
            });
            if (btn) btn.classList.add('active');
            filterList();
        }

        function filterList() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            const rows = document.querySelectorAll('.issue-row');
            let visible = 0;

            rows.forEach(row => {
                const text = row.innerText.toLowerCase();
                const direction = row.getAttribute('data-direction');
                const hasPhone = row.getAttribute('data-has-phone') === 'true';
                const hasVoice = row.getAttribute('data-has-voice') === 'true';

                let matchesCat = true;
                if (currentCategory === 'chorva' && direction !== 'chorva') matchesCat = false;
                if (currentCategory === 'parranda' && direction !== 'parranda') matchesCat = false;
                if (currentCategory === 'phone' && !hasPhone) matchesCat = false;
                if (currentCategory === 'voice' && !hasVoice) matchesCat = false;

                const matchesQuery = text.includes(query);

                if (matchesCat && matchesQuery) {
                    row.style.display = 'flex';
                    visible++;
                } else {
                    row.style.display = 'none';
                }
            });

            document.getElementById('displayCount').innerText = visible + ' ta anketalar';
        }

        function toggleRow(id) {
            const el = document.getElementById('details-' + id);
            if (el) el.classList.toggle('open');
        }

        let allOpen = false;
        function toggleAll() {
            allOpen = !allOpen;
            document.querySelectorAll('.issue-details').forEach(d => {
                if (allOpen) d.classList.add('open');
                else d.classList.remove('open');
            });
        }
    </script>
</body>
</html>
"""

# ----------------- REPO 2: ANALYSIS (NLP & CATEGORIES) -----------------
ANALYSIS_HTML = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>fermamax/analysis: Muammolar Tahlili</title>
    <link rel="icon" type="image/svg+xml" href="/logo.svg">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script>
        if (window.Telegram && window.Telegram.WebApp) {
            try { window.Telegram.WebApp.ready(); window.Telegram.WebApp.expand(); } catch(e) {}
        }
    </script>
    <style>
        """ + COMMON_CSS + """
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }
        @media (max-width: 820px) {
            .grid-2 { grid-template-columns: 1fr; }
        }
        .metric-card {
            background: #ffffff;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            padding: 18px 20px;
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .metric-icon {
            width: 44px;
            height: 44px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            background: #f6f8fa;
            border: 1px solid #d0d7de;
        }
        .metric-info h4 { font-size: 12px; color: #656d76; font-weight: 600; text-transform: uppercase; margin-bottom: 2px; }
        .metric-info .value { font-size: 22px; font-weight: 700; color: #1f2328; }
        .metric-info .sub { font-size: 12px; color: #656d76; }

        .progress-track {
            background-color: #ebedf0;
            border-radius: 6px;
            height: 8px;
            overflow: hidden;
            margin-top: 6px;
        }
        .progress-fill {
            height: 100%;
            border-radius: 6px;
        }
        .problem-bar-item { margin-bottom: 14px; }
        .problem-bar-item:last-child { margin-bottom: 0; }
        .problem-bar-header {
            display: flex;
            justify-content: space-between;
            font-size: 13px;
            font-weight: 600;
            margin-bottom: 4px;
        }

        .kw-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background-color: #f6f8fa;
            border: 1px solid #d0d7de;
            border-radius: 20px;
            padding: 4px 10px;
            font-size: 12px;
            margin: 3px;
        }
        .kw-count {
            background: #afb8c133;
            border-radius: 10px;
            padding: 1px 6px;
            font-size: 11px;
            font-weight: 600;
        }
    </style>
</head>
<body>
    {{navbar_placeholder}}

    <div class="container">
        <!-- 1. Asosiy ko'rsatkichlar kartalari -->
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:16px;margin-bottom:20px;">
            <div class="metric-card">
                <div class="metric-icon" style="background:#ffebe9;border-color:#ff8182;">🚨</div>
                <div class="metric-info">
                    <h4>1-Raqamli Muammo</h4>
                    <div class="value">{{top_pain_title}}</div>
                    <div class="sub">{{top_pain_percentage}}% fermerlar shu dardni aytgan</div>
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-icon" style="background:#dafbe1;border-color:#4ac26b;">🎯</div>
                <div class="metric-info">
                    <h4>Eng ko'p takrorlangan so'z</h4>
                    <div class="value">"{{top_keyword_word}}"</div>
                    <div class="sub">{{top_keyword_count}} marta matn/ovozda tilga olingan</div>
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-icon" style="background:#ddf4ff;border-color:#54aeff;">🚪</div>
                <div class="metric-info">
                    <h4>Klub a'zolari (Guruhga kirgan)</h4>
                    <div class="value">{{group_joins_count}} ta</div>
                    <div class="sub">{{referred_joins_count}} ta fermer do'st taklifi orqali kelgan</div>
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-icon" style="background:#fbefff;border-color:#d2a8ff;">🎙</div>
                <div class="metric-info">
                    <h4>Ovozli javoblar</h4>
                    <div class="value">{{with_voice}} ta</div>
                    <div class="sub">{{total}} tadan {{with_voice}} tasi audio orqali</div>
                </div>
            </div>
        </div>

        <!-- 2. Muammolar taqsimoti va Kalit so'zlar -->
        <div class="grid-2">
            <div class="Box">
                <div class="Box-header">
                    <div>📊 Eng ko'p uchrayotgan muammolar reytingi</div>
                </div>
                <div class="Box-body">
                    {{problem_bars}}
                </div>
            </div>

            <div class="Box">
                <div class="Box-header">
                    <div>🔤 Fermerlar leksikoni: Eng ko'p ishlatilgan kalit so'zlar</div>
                </div>
                <div class="Box-body">
                    <p style="font-size:12px;color:#656d76;margin-bottom:12px;">
                        Fermerlar o'z ovozlari va xabarlarida eng ko'p ishlatgan so'zlar (stop-words filtrlangan):
                    </p>
                    <div>
                        {{keywords_pills}}
                    </div>
                </div>
            </div>
        </div>

        <!-- 3. Chorva vs Parranda solishtiruvi -->
        <div class="grid-2">
            <div class="Box">
                <div class="Box-header">
                    <div>🐄 Chorvadorlarning asosiy muammolari ({{chorva_total}} ta)</div>
                </div>
                <div class="Box-body">
                    {{chorva_bars}}
                </div>
            </div>

            <div class="Box">
                <div class="Box-header">
                    <div>🐔 Parrandachilarning asosiy muammolari ({{parranda_total}} ta)</div>
                </div>
                <div class="Box-body">
                    {{parranda_bars}}
                </div>
            </div>
        </div>

        <!-- 4. Fermerlar miqyosi bo'yicha -->
        <div class="Box">
            <div class="Box-header">
                <div>👥 Kimlarda bu muammo ko'proq uchrayapti? (Xo'jalik miqyosi)</div>
            </div>
            <div class="Box-body">
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:16px;">
                    {{segment_cards}}
                </div>
            </div>
        </div>

    </div>
</body>
</html>
"""

# ----------------- REPO 3: MEMBERS & REFERRALS (GURUHGA QO'SHILGANLAR) -----------------
MEMBERS_HTML = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>fermamax/members: Guruh a'zolari va Takliflar</title>
    <link rel="icon" type="image/svg+xml" href="/logo.svg">
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script>
        if (window.Telegram && window.Telegram.WebApp) {
            try { window.Telegram.WebApp.ready(); window.Telegram.WebApp.expand(); } catch(e) {}
        }
    </script>
    <style>
        """ + COMMON_CSS + """
        .metric-card {
            background: #ffffff;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            padding: 16px 20px;
            display: flex;
            align-items: center;
            gap: 16px;
        }
        .metric-icon {
            width: 44px;
            height: 44px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            background: #f6f8fa;
            border: 1px solid #d0d7de;
        }
        .metric-info h4 { font-size: 12px; color: #656d76; font-weight: 600; text-transform: uppercase; margin-bottom: 2px; }
        .metric-info .value { font-size: 22px; font-weight: 700; color: #1f2328; }
        .metric-info .sub { font-size: 12px; color: #656d76; }

        .leaderboard-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 14px;
            border-bottom: 1px solid #d0d7de;
            font-size: 13px;
        }
        .leaderboard-row:last-child { border-bottom: none; }
        .leaderboard-user {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .rank-badge {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: #f6f8fa;
            border: 1px solid #d0d7de;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 11px;
        }
        .rank-1 { background: #fff8c5; border-color: #d4a72c; color: #9a6700; }
        .rank-2 { background: #f6f8fa; border-color: #afb8c1; color: #24292f; }
        .rank-3 { background: #ffebe9; border-color: #ff8182; color: #cf222e; }

        .joins-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .joins-table th {
            background-color: #f6f8fa;
            color: #656d76;
            font-weight: 600;
            text-align: left;
            padding: 8px 14px;
            border-bottom: 1px solid #d0d7de;
        }
        .joins-table td {
            padding: 10px 14px;
            border-bottom: 1px solid #d0d7de;
            vertical-align: middle;
        }
        .joins-table tr:hover { background-color: #f6f8fa; }
        .joins-table tr:last-child td { border-bottom: none; }

        .search-box { margin-bottom: 16px; position: relative; }
        .search-box svg { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); fill: #656d76; }
        .search-input {
            width: 100%;
            padding: 6px 12px 6px 32px;
            font-size: 14px;
            background-color: #ffffff;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            outline: none;
        }
        .search-input:focus { border-color: #0969da; box-shadow: 0 0 0 3px rgba(9, 105, 218, 0.2); }
    </style>
</head>
<body>
    {{navbar_placeholder}}

    <div class="container">
        <!-- Metric kartalar -->
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(240px, 1fr));gap:16px;margin-bottom:20px;">
            <div class="metric-card">
                <div class="metric-icon" style="background:#dafbe1;border-color:#4ac26b;">👥</div>
                <div class="metric-info">
                    <h4>Jami Guruh A'zolari</h4>
                    <div class="value">{{group_joins_count}} ta</div>
                    <div class="sub">Telegram guruhga qo'shilganlar</div>
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-icon" style="background:#ddf4ff;border-color:#54aeff;">🔗</div>
                <div class="metric-info">
                    <h4>Do'stlar taklifi orqali</h4>
                    <div class="value">{{referred_joins_count}} ta</div>
                    <div class="sub">1 martalik taklif havolasi orqali</div>
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-icon" style="background:#fff8c5;border-color:#d4a72c;">⚡</div>
                <div class="metric-info">
                    <h4>To'g'ridan-to'g'ri (CustDev)</h4>
                    <div class="value">{{direct_joins_count}} ta</div>
                    <div class="sub">Anketa yakunidagi 1 martalik havola</div>
                </div>
            </div>
        </div>

        <div style="display:grid;grid-template-columns: 360px 1fr; gap: 20px; align-items: flex-start;">
            <!-- Top Taklifchilar Reytingi -->
            <div class="Box">
                <div class="Box-header">
                    <div>🏆 Eng faol do'st taklif qilganlar</div>
                </div>
                <div style="padding: 0;">
                    {{leaderboard_rows}}
                </div>
            </div>

            <!-- Guruhga qo'shilishlar jurnali (Audit log) -->
            <div class="Box">
                <div class="Box-header">
                    <div>📋 Guruhga qo'shilganlar jurnali (Jonli qaydlar)</div>
                    <span style="font-size:12px;color:#656d76;">{{group_joins_count}} ta yozuv</span>
                </div>
                <div class="Box-body" style="padding-bottom: 0;">
                    <div class="search-box">
                        <svg height="14" viewBox="0 0 16 16" width="14"><path d="M10.68 11.74a6 6 0 0 1-7.922-8.982 6 6 0 0 1 8.982 7.922l3.04 3.04a.749.749 0 0 1-.326 1.275.749.749 0 0 1-.734-.215ZM11.5 7a4.5 4.5 0 1 0-9 0 4.5 4.5 0 0 0 9 0Z"></path></svg>
                        <input type="text" id="memberSearch" class="search-input" placeholder="Qidiruv (fermer, username, taklif qilgan)..." onkeyup="filterMembers()">
                    </div>
                </div>
                <div style="overflow-x: auto;">
                    <table class="joins-table" id="membersTable">
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Fermer</th>
                                <th>Username / ID</th>
                                <th>Qo'shilgan vaqti</th>
                                <th>Taklif qiluvchi (Referral)</th>
                                <th>Havola holati</th>
                            </tr>
                        </thead>
                        <tbody>
                            {{joins_rows}}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script>
        function filterMembers() {
            const query = document.getElementById('memberSearch').value.toLowerCase();
            const rows = document.querySelectorAll('#membersTable tbody tr');
            rows.forEach(r => {
                const text = r.innerText.toLowerCase();
                r.style.display = text.includes(query) ? '' : 'none';
            });
        }
    </script>
</body>
</html>
"""

# ==================== HANDLERS ====================

async def handle_login(request: web.Request):
    if is_authenticated(request):
        raise web.HTTPFound("/")

    logo_svg = render_logo_svg(size=64, color="#000000")

    if request.method == "POST":
        data = await request.post()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            response = web.HTTPFound("/")
            token = generate_auth_token()
            response.set_cookie("gh_auth", token, max_age=86400 * 30, httponly=True)
            return response
        else:
            error_html = '<div class="error-alert">Username yoki parol noto\'g\'ri kiritildi!</div>'
            html = LOGIN_HTML.replace("{{error_block}}", error_html).replace("{{fermamax_logo_large}}", logo_svg)
            return web.Response(text=html, content_type="text/html")

    html = LOGIN_HTML.replace("{{error_block}}", "").replace("{{fermamax_logo_large}}", logo_svg)
    return web.Response(text=html, content_type="text/html")

async def handle_logout(request: web.Request):
    response = web.HTTPFound("/login")
    response.del_cookie("gh_auth")
    return response

async def handle_logo_svg(request: web.Request):
    svg_code = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 591 590.84"><path fill="#000000" d="{LOGO_PATH_D}"/></svg>'
    return web.Response(text=svg_code, content_type="image/svg+xml")

def render_audio_widget(v_path: str) -> str:
    if not v_path:
        return ""
    basename = os.path.splitext(v_path)[0]
    wav_name = f"{basename}.wav"
    ogg_name = v_path if v_path.endswith(".ogg") else f"{v_path}.ogg"
    return f"""
    <div class="audio-player-box">
        <span style="font-size:12px;color:#8250df;font-weight:600;white-space:nowrap;">🎙 Audio:</span>
        <audio controls preload="metadata" style="height:32px;flex:1;max-width:380px;">
            <source src="/voices/{wav_name}" type="audio/wav">
            <source src="/voices/{ogg_name}" type="audio/ogg">
            Brauzeringiz audioni qo'llab-quvvatlamadi.
        </audio>
        <a href="/voices/{wav_name}" download="{wav_name}" class="btn-gh-primary" style="padding:2px 8px;font-size:11px;background:#656d76;" title="Yuklab olish">⬇️</a>
    </div>
    """

async def handle_voice(request: web.Request):
    """
    Ovozli xabarlarni Safari, Chrome va barcha brauzerlarda to'liq o'qish uchun audio endpoint.
    Safari ogg formatini o'qiy olmagani uchun avtomatik WAV formatiga o'girib uzatadi.
    """
    filename = os.path.basename(request.match_info.get("filename", ""))
    filepath = os.path.join(VOICE_DIR, filename)

    # 1. Agar WAV so'ralgan bo'lsa va mavjud bo'lmasa, OGG dan o'girish (macOS da afconvert, Linuxda ffmpeg)
    if filename.endswith(".wav") and not os.path.isfile(filepath):
        ogg_source = os.path.splitext(filepath)[0] + ".ogg"
        if os.path.isfile(ogg_source):
            import subprocess
            import shutil
            if os.path.exists("/usr/bin/afconvert"):
                subprocess.run(
                    ["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16", ogg_source, filepath],
                    capture_output=True
                )
            elif shutil.which("ffmpeg"):
                subprocess.run(
                    ["ffmpeg", "-y", "-i", ogg_source, filepath],
                    capture_output=True
                )

    if os.path.isfile(filepath):
        content_type = "audio/wav" if filename.endswith(".wav") else "audio/ogg"
        return web.FileResponse(filepath, headers={
            "Content-Type": content_type,
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=86400"
        })
    return web.Response(status=404, text="Ovozli fayl topilmadi")

# ----------------- REPO 1 HANDLER: / (CUSTDEV JAVOBLAR) -----------------
async def handle_index(request: web.Request):
    if not is_authenticated(request):
        raise web.HTTPFound("/login")

    stats = await get_stats()
    rows = await get_all_responses()

    items_html = []
    for idx, r in enumerate(rows, 1):
        resp_id = r.get("id") or idx
        direction = r.get("direction", "chorva")
        dir_class = "label-chorva" if direction == "chorva" else "label-parranda"
        dir_label = "🐄 chorva" if direction == "chorva" else "🐔 parranda"

        phone = r.get("phone_number") or ""
        phone_html = f'<span class="gh-label label-phone">📞 {html_lib.escape(phone)}</span>' if phone else ''
        has_phone = "true" if phone else "false"

        # Ovozli xabar bor-yo'qligi
        p_v = r.get("problem_voice_path")
        s_v = r.get("solution_voice_path")
        d_v = r.get("dissatisfaction_voice_path")
        has_voice = bool(p_v or s_v or d_v or r.get("problem_voice_id"))
        voice_badge = '<span class="gh-label label-voice">🎙 Ovozli</span>' if has_voice else ''

        # Referral ma'lumoti
        ref_name = r.get("referrer_name")
        ref_badge = f'<span class="gh-label label-ref">🔗 Taklif: {html_lib.escape(ref_name)}</span>' if ref_name else ''

        username = f"@{r['username']}" if r.get("username") else "—"
        full_name = html_lib.escape(r.get("full_name") or "Noma'lum fermer")

        problem_text = (r.get("problem") or "") + " " + (r.get("dissatisfaction") or "")
        cat_key = detect_category(problem_text)
        cat_title = CATEGORIES[cat_key]["title"]

        raw_problem = r.get("problem") or "Muammo yozilmagan"
        preview_problem = html_lib.escape(raw_problem[:90] + ("..." if len(raw_problem) > 90 else ""))

        # 2-savol audio
        problem_audio_html = render_audio_widget(p_v)

        # 3-savol audio
        solution_audio_html = render_audio_widget(s_v)

        # 4-savol audio
        dissatisfaction_audio_html = render_audio_widget(d_v)

        # Referral info block
        referrer_box = ""
        if ref_name:
            u_info = f" (@{r.get('referrer_username')})" if r.get('referrer_username') else ""
            referrer_box = f"""
            <div class="qa-block" style="background:#f0f9ff;border:1px dashed #7dd3fc;border-radius:6px;padding:8px 12px;margin-bottom:12px;">
                <span style="color:#0284c7;font-weight:600;">🔗 Taklif qilgan fermer:</span> 
                <strong>{html_lib.escape(ref_name)}</strong>{html_lib.escape(u_info)}
            </div>
            """

        item = f"""
        <div class="issue-row" data-direction="{direction}" data-has-phone="{has_phone}" data-has-voice="{str(has_voice).lower()}">
            <svg class="issue-icon" height="16" viewBox="0 0 16 16" width="16"><path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"></path></svg>
            <div class="issue-content">
                <div class="issue-header-line">
                    <span class="issue-author" onclick="toggleRow({resp_id})">{full_name}</span>
                    <span class="gh-label {dir_class}">{dir_label}</span>
                    <span class="gh-label label-cat">{cat_title}</span>
                    {phone_html}
                    {voice_badge}
                    {ref_badge}
                </div>
                <div class="issue-summary" onclick="toggleRow({resp_id})">
                    {preview_problem}
                </div>
                <div class="issue-meta">
                    <span>#{resp_id}</span>
                    <span>•</span>
                    <span>{username}</span>
                    <span>•</span>
                    <span style="color:#8c959f;">ID: {mask_user_id(r.get('user_id'))}</span>
                    <span>•</span>
                    <span>Hajm: {safe_str(r.get('livestock_count'))}</span>
                    <span>•</span>
                    <span>{safe_datetime(r.get('created_at'))}</span>
                </div>

                <div class="issue-details" id="details-{resp_id}">
                    {referrer_box}
                    <div class="qa-block">
                        <div class="qa-title">1-b. Bosh soni / Parranda hajmi:</div>
                        <div class="qa-text">{safe_str(r.get('livestock_count'))}</div>
                    </div>
                    <div class="qa-block">
                        <div class="qa-title">2-savol: Asosiy muammo (Dard)</div>
                        <div class="qa-text">{safe_str(r.get('problem'))}</div>
                        {problem_audio_html}
                    </div>
                    <div class="qa-block">
                        <div class="qa-title">3-savol: Qanday hal qildi va xarajat</div>
                        <div class="qa-text">{safe_str(r.get('solution_taken'))}</div>
                        {solution_audio_html}
                    </div>
                    <div class="qa-block">
                        <div class="qa-title">4-savol: Yetishmagan jihat / norozilik</div>
                        <div class="qa-text">{safe_str(r.get('dissatisfaction'))}</div>
                        {dissatisfaction_audio_html}
                    </div>
                    <div class="qa-block">
                        <div class="qa-title">Telefon raqam</div>
                        <div class="qa-text" style="font-weight:600; color:#1a7f37;">{safe_str(phone, "Qoldirilmagan")}</div>
                    </div>
                </div>
            </div>
        </div>
        """
        items_html.append(item)

    if not items_html:
        issue_items = '<div class="empty-state"><h3>Hozircha hech qanday javob kelib tushmagan</h3></div>'
    else:
        issue_items = "\n".join(items_html)

    logo_small = render_logo_svg(size=24, color="#000000")
    navbar_html = render_navbar("custdev", stats["total"], stats["group_joins_count"], logo_small)

    html = (
        CUSTDEV_HTML
        .replace("{{navbar_placeholder}}", navbar_html)
        .replace("{{total}}", str(stats["total"]))
        .replace("{{chorva}}", str(stats["chorva"]))
        .replace("{{parranda}}", str(stats["parranda"]))
        .replace("{{with_phone}}", str(stats["with_phone"]))
        .replace("{{with_voice}}", str(stats["with_voice"]))
        .replace("{{group_joins_count}}", str(stats["group_joins_count"]))
        .replace("{{issue_items}}", issue_items)
    )
    return render_html_response(request, html)

# ----------------- REPO 2 HANDLER: /analysis (MUAMMOLAR TAHLILI) -----------------
async def handle_analysis(request: web.Request):
    if not is_authenticated(request):
        raise web.HTTPFound("/login")

    stats = await get_stats()
    rows = await get_all_responses()
    analytics = analyze_custdev(rows)

    total = analytics["total"]

    # 1. Top Pain title & percentage
    top_pain_title = "Hozircha yo'q"
    top_pain_pct = 0
    if analytics["categories"] and total > 0:
        first = analytics["categories"][0]
        if first["count"] > 0:
            top_pain_title = first["title"]
            top_pain_pct = first["percentage"]

    # 2. Top keyword
    top_kw_word = "—"
    top_kw_cnt = 0
    if analytics["top_keywords"]:
        top_kw_word = analytics["top_keywords"][0][0]
        top_kw_cnt = analytics["top_keywords"][0][1]

    # 3. Overall problem bars
    problem_bars = []
    for cat in analytics["categories"]:
        if total == 0 and cat["key"] != "em_narxi":
            continue
        bar = f"""
        <div class="problem-bar-item">
            <div class="problem-bar-header">
                <span>{cat['title']}</span>
                <span>{cat['percentage']}% <small style="color:#656d76;">({cat['count']} ta fermer)</small></span>
            </div>
            <div class="progress-track">
                <div class="progress-fill" style="width: {cat['percentage']}%; background: {cat['color']};"></div>
            </div>
        </div>
        """
        problem_bars.append(bar)
    problem_bars_html = "\n".join(problem_bars) if problem_bars else "<p style='color:#656d76;'>Hozircha ma'lumot yo'q</p>"

    # 4. Keywords pills
    kw_pills = []
    for word, cnt in analytics["top_keywords"]:
        pill = f'<span class="kw-pill">{html_lib.escape(word)} <span class="kw-count">{cnt}</span></span>'
        kw_pills.append(pill)
    keywords_pills_html = "\n".join(kw_pills) if kw_pills else "<p style='color:#656d76;'>Hozircha kalit so'zlar yetarli emas</p>"

    # 5. Chorva vs Parranda bars
    def build_bars(cats_list):
        res = []
        for cat in cats_list[:4]:
            if cat["count"] == 0:
                continue
            res.append(f"""
            <div style="margin-bottom:12px;">
                <div style="display:flex;justify-content:space-between;font-size:13px;font-weight:600;margin-bottom:4px;">
                    <span>{cat['title']}</span>
                    <span>{cat['count']} ta</span>
                </div>
                <div class="progress-track">
                    <div class="progress-fill" style="width: {cat['percentage']}%; background: {cat['color']};"></div>
                </div>
            </div>
            """)
        return "\n".join(res) if res else "<p style='color:#656d76;'>Ma'lumot yo'q</p>"

    chorva_bars_html = build_bars(analytics["chorva_stats"]["categories"])
    parranda_bars_html = build_bars(analytics["parranda_stats"]["categories"])

    # 6. Segment Cards
    seg_cards = []
    segment_names = [
        ("Chorva: Kichik (1-10 bosh)", "🐄 Kichik chorvador", "1-10 bosh mol/qo'y"),
        ("Chorva: O'rta (11-50 bosh)", "🐄 O'rta fermer", "11-50 bosh mol/qo'y"),
        ("Chorva: Yirik (50+ bosh)", "🐄 Yirik kompleks", "50 dan ortiq mol/qo'y"),
        ("Parranda: Kichik (1-100 tovuq)", "🐔 Xonadon parrandasi", "1-100 ta tovuq"),
        ("Parranda: O'rta (101-1000 tovuq)", "🐔 O'rta parrandachi", "101-1000 ta tovuq"),
        ("Parranda: Yirik (1000+ tovuq)", "🐔 Yirik parrandachilik", "1000 dan ortiq tovuq"),
    ]

    for full_seg, label, sub in segment_names:
        cnt = analytics["segment_counts"].get(full_seg, 0)
        cross_probs = analytics["cross_table"].get(full_seg, {})
        top_prob_title = "Aniqlanmagan"
        if cross_probs:
            sorted_probs = sorted(cross_probs.items(), key=lambda x: x[1], reverse=True)
            if sorted_probs and sorted_probs[0][1] > 0:
                top_key = sorted_probs[0][0]
                top_prob_title = CATEGORIES[top_key]["title"]

        card = f"""
        <div style="background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;padding:14px;">
            <div style="font-weight:600;font-size:14px;margin-bottom:2px;">{label}</div>
            <div style="font-size:12px;color:#656d76;margin-bottom:10px;">{sub}</div>
            <div style="display:flex;justify-content:space-between;margin-bottom:6px;font-size:13px;">
                <span>Anketa to'ldirganlar:</span>
                <strong>{cnt} ta</strong>
            </div>
            <div style="font-size:12px;color:#1f2328;background:#ffffff;border:1px solid #e1e4e8;border-radius:4px;padding:6px 8px;">
                Asosiy dardi: <strong style="color:#cf222e;">{top_prob_title}</strong>
            </div>
        </div>
        """
        seg_cards.append(card)
    segment_cards_html = "\n".join(seg_cards)

    logo_small = render_logo_svg(size=24, color="#000000")
    navbar_html = render_navbar("analysis", stats["total"], stats["group_joins_count"], logo_small)

    html = (
        ANALYSIS_HTML
        .replace("{{navbar_placeholder}}", navbar_html)
        .replace("{{total}}", str(stats["total"]))
        .replace("{{top_pain_title}}", top_pain_title)
        .replace("{{top_pain_percentage}}", str(top_pain_pct))
        .replace("{{top_keyword_word}}", top_kw_word)
        .replace("{{top_keyword_count}}", str(top_kw_cnt))
        .replace("{{group_joins_count}}", str(stats["group_joins_count"]))
        .replace("{{referred_joins_count}}", str(stats["referred_joins_count"]))
        .replace("{{with_voice}}", str(stats["with_voice"]))
        .replace("{{problem_bars}}", problem_bars_html)
        .replace("{{keywords_pills}}", keywords_pills_html)
        .replace("{{chorva_total}}", str(analytics["chorva_stats"]["total"]))
        .replace("{{chorva_bars}}", chorva_bars_html)
        .replace("{{parranda_total}}", str(analytics["parranda_stats"]["total"]))
        .replace("{{parranda_bars}}", parranda_bars_html)
        .replace("{{segment_cards}}", segment_cards_html)
    )
    return render_html_response(request, html)

# ----------------- REPO 3 HANDLER: /members (GURUH A'ZOLARI & TAKLIFLAR) -----------------
async def handle_members(request: web.Request):
    if not is_authenticated(request):
        raise web.HTTPFound("/login")

    stats = await get_stats()
    group_joins = await get_group_joins(limit=150)
    top_referrers = await get_top_referrers(limit=10)

    direct_count = max(0, stats["group_joins_count"] - stats["referred_joins_count"])

    # Top referrers HTML
    lb_rows = []
    if top_referrers:
        for idx, tr in enumerate(top_referrers, 1):
            rank_class = f"rank-{idx}" if idx <= 3 else ""
            u_text = f"@{tr['username']}" if tr.get("username") else "username yo'q"
            row = f"""
            <div class="leaderboard-row">
                <div class="leaderboard-user">
                    <div class="rank-badge {rank_class}">{idx}</div>
                    <div>
                        <div style="font-weight:600;color:#1f2328;">{safe_str(tr.get('full_name'))}</div>
                        <div style="font-size:11px;color:#656d76;">{safe_str(u_text)} • ID: {mask_user_id(tr.get('user_id'))}</div>
                    </div>
                </div>
                <div>
                    <span class="gh-label label-ref" style="font-size:12px;font-weight:600;">{tr.get('referral_count', 0)} ta do'st</span>
                </div>
            </div>
            """
            lb_rows.append(row)
    else:
        lb_rows.append('<div style="padding:24px 16px;text-align:center;color:#656d76;">Hozircha hech kim do\'stini taklif qilmadi</div>')
    leaderboard_html = "\n".join(lb_rows)

    # Joins table rows
    join_tr_list = []
    for idx, j in enumerate(group_joins, 1):
        uname = f"@{j['username']}" if j.get('username') else "—"
        inviter_html = '<span style="color:#656d76;">To\'g\'ridan-to\'g\'ri (CustDev)</span>'
        if j.get("inviter_name"):
            inv_uname = f" (@{j['inviter_username']})" if j.get("inviter_username") else ""
            inviter_html = f'<span class="gh-label label-ref">🔗 {safe_str(j.get("inviter_name"))}{safe_str(inv_uname, "")}</span>'

        link_type = '<span class="gh-badge" style="background:#dafbe1;color:#1a7f37;border-color:#4ac26b;">1 martalik ishlatildi</span>' if j.get("invite_link") else '<span class="gh-badge">Standart</span>'

        tr = f"""
        <tr>
            <td style="color:#656d76;">#{j.get('id', idx)}</td>
            <td><strong>{safe_str(j.get('full_name'))}</strong></td>
            <td><code>{safe_str(uname)}</code> <small style="color:#656d76;">({mask_user_id(j.get('user_id'))})</small></td>
            <td>{safe_datetime(j.get('joined_at'))}</td>
            <td>{inviter_html}</td>
            <td>{link_type}</td>
        </tr>
        """
        join_tr_list.append(tr)

    if not join_tr_list:
        joins_html = '<tr><td colspan="6" style="text-align:center;padding:32px;color:#656d76;">Hozircha guruhga hech kim qo\'shilmagan</td></tr>'
    else:
        joins_html = "\n".join(join_tr_list)

    logo_small = render_logo_svg(size=24, color="#000000")
    navbar_html = render_navbar("members", stats["total"], stats["group_joins_count"], logo_small)

    html = (
        MEMBERS_HTML
        .replace("{{navbar_placeholder}}", navbar_html)
        .replace("{{group_joins_count}}", str(stats["group_joins_count"]))
        .replace("{{referred_joins_count}}", str(stats["referred_joins_count"]))
        .replace("{{direct_joins_count}}", str(direct_count))
        .replace("{{leaderboard_rows}}", leaderboard_html)
        .replace("{{joins_rows}}", joins_html)
    )
    return render_html_response(request, html)

# ----------------- CSV EXPORT HANDLER -----------------
async def handle_download_csv(request: web.Request):
    if not is_authenticated(request):
        raise web.HTTPFound("/login")

    rows = await get_all_responses()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "User ID", "Ism-familiya", "Username", "Yo'nalish",
        "Hajm (bosh soni)", "Aniqlangan Muammo Toifasi", "2-Muammo", "2-Muammo Ovozli Fayl",
        "3-Yechim & Xarajat", "3-Yechim Ovozli Fayl",
        "4-Yetishmagan jihat", "4-Yetishmagan Ovozli Fayl",
        "Telefon", "Taklif qilgan (Referral)", "Vaqt"
    ])
    for r in rows:
        problem_text = (r.get("problem") or "") + " " + (r.get("dissatisfaction") or "")
        cat_key = detect_category(problem_text)
        cat_title = CATEGORIES[cat_key]["title"]
        writer.writerow([
            r.get("id"), r.get("user_id"), r.get("full_name"), r.get("username"),
            r.get("direction"), r.get("livestock_count"), cat_title, 
            r.get("problem"), r.get("problem_voice_path"),
            r.get("solution_taken"), r.get("solution_voice_path"),
            r.get("dissatisfaction"), r.get("dissatisfaction_voice_path"),
            r.get("phone_number"), r.get("referrer_name"),
            r.get("created_at")
        ])

    return web.Response(
        text=output.getvalue(),
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="custdev_javoblari.csv"'}
    )

async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text="OK", content_type="text/plain")

@web.middleware
async def error_middleware(request: web.Request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as e:
        import traceback
        import logging
        err_tb = traceback.format_exc()
        logging.getLogger(__name__).error(f"ADMIN PANEL XATOLIK ({request.path}):\n{err_tb}")
        err_msg = html_lib.escape(str(e))
        html = f"""<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="utf-8">
    <title>Server Xatosi (500)</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #fff5f5; color: #1f2328; padding: 40px 20px; max-width: 800px; margin: 0 auto; }}
        .card {{ background: #fff; border: 1px solid #fed7d7; border-radius: 8px; padding: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
        h2 {{ color: #c53030; margin-bottom: 12px; }}
        pre {{ background: #2d3748; color: #f7fafc; padding: 14px; border-radius: 6px; overflow-x: auto; font-size: 13px; line-height: 1.4; }}
        .btn {{ display: inline-block; margin-top: 16px; padding: 8px 16px; background: #0969da; color: #fff; text-decoration: none; border-radius: 6px; font-weight: 500; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>⚠️ Serverda xatolik yuz berdi (500)</h2>
        <p><strong>Xatolik:</strong> <code>{err_msg}</code></p>
        <p><strong>So'rov manzili:</strong> <code>{html_lib.escape(request.path)}</code></p>
        <h4 style="margin-top:16px;">Tafsilot (Traceback):</h4>
        <pre>{html_lib.escape(err_tb)}</pre>
        <a href="/" class="btn">Bosh sahifaga qaytish</a>
        <a href="/login" class="btn" style="background:#656d76;margin-left:8px;">Qayta kirish</a>
    </div>
</body>
</html>"""
        return web.Response(status=500, text=html, content_type="text/html")

def create_admin_app():
    app = web.Application(middlewares=[error_middleware])
    app.router.add_get("/health", handle_health)
    app.router.add_get("/", handle_index)
    app.router.add_get("/analysis", handle_analysis)
    app.router.add_get("/members", handle_members)
    app.router.add_get("/login", handle_login)
    app.router.add_post("/login", handle_login)
    app.router.add_get("/logout", handle_logout)
    app.router.add_get("/logo.svg", handle_logo_svg)
    app.router.add_get("/voices/{filename}", handle_voice)
    app.router.add_get("/download-csv", handle_download_csv)
    return app

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db())
    app = create_admin_app()
    print("🚀 Fermamax GitHub-Style Admin Panel: http://localhost:8080")
    web.run_app(app, port=8080)
