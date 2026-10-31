import re
from collections import Counter

CATEGORIES = {
    "em_narxi": {
        "title": "🌾 Em-xashak va ozuqa qimmatligi",
        "keywords": ["em", "yem", "pichan", "somon", "ozuqa", "qimmat", "narx", "kombikorm", "sheluxa", "bug'doy", "arpa"],
        "color": "#f59e0b"
    },
    "kasallik": {
        "title": "🦠 Kasallik va nobud bo'lish",
        "keywords": ["kasal", "nobud", "o'lim", "shol", "ich ket", "shamollash", "infektsiya", "vaktsina", "zarar", "o'ldi", "harorat"],
        "color": "#ef4444"
    },
    "veterinar": {
        "title": "👨‍⚕️ Veterinar va sifatli dori topilmasligi",
        "keywords": ["veterinar", "vrach", "doktor", "mutaxassis", "dori", "ukol", "tashxis", "yordam", "dorilar", "apteka"],
        "color": "#8b5cf6"
    },
    "bozor_savdo": {
        "title": "💰 Mahsulotni sotolmaslik / Bozor pastligi",
        "keywords": ["sot", "sotolmadim", "mijoz", "bozor", "narx tushdi", "sut oluvchi", "tuxum", "go'sht", "arzon", "xaridor"],
        "color": "#3b82f6"
    },
    "joja_nasl": {
        "title": "🐣 Jo'ja / Nasl / Zot sifati va topilmasligi",
        "keywords": ["jo'ja", "nasl", "zot", "urug'", "inkubator", "parvarish", "urug'lantirish"],
        "color": "#ec4899"
    },
    "boshqa": {
        "title": "⚙️ Boshqa tashkiliy muammolar",
        "keywords": [],
        "color": "#64748b"
    }
}

STOP_WORDS = {
    "va", "bu", "bilan", "uchun", "da", "ham", "deb", "bir", "haqida", "yoki",
    "men", "biz", "siz", "ular", "u", "shu", "lekin", "ammo", "chunki", "edi",
    "ekan", "bo'ldi", "boldi", "kerak", "esa", "o'z", "ozi", "ozim", "faqat",
    "juda", "ko'p", "kop", "ozgina", "yana", "bor", "yo'q", "yoq", "qilib",
    "qildim", "qildik", "berdi", "bo'lgan", "bolgan", "bo'lsa", "bolsa",
    "ketti", "ketdi", "tushdi", "ovozli", "xabar", "aytgan", "boladi",
    "bo'ladi", "bomasa", "bormi", "nima", "qanaqa", "qanday", "qachon"
}

def parse_count(count_str: str) -> int:
    """Hajm / bosh sonini raqamga aylantiradi."""
    if not count_str:
        return 0
    nums = re.findall(r'\d+', count_str)
    if nums:
        return int(nums[0])
    return 0

def detect_category(text: str) -> str:
    """Matn ichidagi kalit so'zlar bo'yicha muammo toifasini aniqlaydi."""
    if not text:
        return "boshqa"
    text_lower = text.lower()
    for cat_key, cat_data in CATEGORIES.items():
        if cat_key == "boshqa":
            continue
        for kw in cat_data["keywords"]:
            if kw in text_lower:
                return cat_key
    return "boshqa"

def extract_top_keywords(responses: list, top_n=24) -> list:
    """Barcha javoblar matnidan eng ko'p takrorlangan so'zlarni ajratadi."""
    words = []
    for r in responses:
        full_text = f"{r.get('problem', '')} {r.get('solution_taken', '')} {r.get('dissatisfaction', '')}"
        cleaned = re.sub(r"[^a-zA-Z0-9а-яА-ЯўқғҳЎҚҒҲ\s\']", " ", full_text.lower())
        tokens = cleaned.split()
        for tok in tokens:
            tok = tok.strip("'").strip('"')
            if len(tok) >= 3 and tok not in STOP_WORDS:
                words.append(tok)
    return Counter(words).most_common(top_n)

def analyze_custdev(responses: list) -> dict:
    """CustDev bo'yicha to'liq va chuqur tahlil chiqaradi."""
    total = len(responses)
    if total == 0:
        return {
            "total": 0,
            "categories": [],
            "top_keywords": [],
            "segment_counts": {"Kichik": 0, "O'rta": 0, "Yirik": 0},
            "chorva_stats": {"total": 0, "categories": []},
            "parranda_stats": {"total": 0, "categories": []},
            "cross_table": {},
            "call_leads": []
        }

    # 1. Umumiy toifalar
    cat_counts = {k: 0 for k in CATEGORIES.keys()}
    
    # 2. Yo'nalishlar bo'yicha alohida
    chorva_cats = {k: 0 for k in CATEGORIES.keys()}
    parranda_cats = {k: 0 for k in CATEGORIES.keys()}
    chorva_total = 0
    parranda_total = 0

    # 3. Segmentlar
    segment_counts = {
        "Kichik xo'jaliklar (1-10 bosh / 1-100 tovuq)": 0,
        "O'rta xo'jaliklar (10-50 bosh / 100-1,000 tovuq)": 0,
        "Yirik xo'jaliklar (50+ bosh / 1,000+ tovuq)": 0,
    }
    cross_table = {}
    call_leads = []

    for r in responses:
        problem_text = f"{r.get('problem', '')} {r.get('dissatisfaction', '')}"
        cat = detect_category(problem_text)
        cat_counts[cat] += 1

        dir_val = r.get("direction", "chorva")
        count_val = parse_count(r.get("livestock_count", "0"))

        if dir_val == "parranda":
            parranda_total += 1
            parranda_cats[cat] += 1
            if count_val <= 100:
                seg_group = "Kichik xo'jaliklar (1-10 bosh / 1-100 tovuq)"
            elif count_val <= 1000:
                seg_group = "O'rta xo'jaliklar (10-50 bosh / 100-1,000 tovuq)"
            else:
                seg_group = "Yirik xo'jaliklar (50+ bosh / 1,000+ tovuq)"
        else:
            chorva_total += 1
            chorva_cats[cat] += 1
            if count_val <= 10:
                seg_group = "Kichik xo'jaliklar (1-10 bosh / 1-100 tovuq)"
            elif count_val <= 50:
                seg_group = "O'rta xo'jaliklar (10-50 bosh / 100-1,000 tovuq)"
            else:
                seg_group = "Yirik xo'jaliklar (50+ bosh / 1,000+ tovuq)"

        segment_counts[seg_group] += 1

        if seg_group not in cross_table:
            cross_table[seg_group] = {k: 0 for k in CATEGORIES.keys()}
        cross_table[seg_group][cat] += 1

        if r.get("phone_number"):
            call_leads.append(r)

    # Toifalarni ro'yxatga keltirish
    categories_list = []
    for k, v in cat_counts.items():
        percentage = round((v / total) * 100, 1) if total > 0 else 0
        categories_list.append({
            "key": k,
            "title": CATEGORIES[k]["title"],
            "count": v,
            "percentage": percentage,
            "color": CATEGORIES[k]["color"]
        })
    categories_list.sort(key=lambda x: x["count"], reverse=True)

    # Chorva toifalari
    chorva_cats_list = []
    for k, v in chorva_cats.items():
        pct = round((v / chorva_total) * 100, 1) if chorva_total > 0 else 0
        chorva_cats_list.append({
            "key": k,
            "title": CATEGORIES[k]["title"],
            "count": v,
            "percentage": pct,
            "color": CATEGORIES[k]["color"]
        })
    chorva_cats_list.sort(key=lambda x: x["count"], reverse=True)

    # Parranda toifalari
    parranda_cats_list = []
    for k, v in parranda_cats.items():
        pct = round((v / parranda_total) * 100, 1) if parranda_total > 0 else 0
        parranda_cats_list.append({
            "key": k,
            "title": CATEGORIES[k]["title"],
            "count": v,
            "percentage": pct,
            "color": CATEGORIES[k]["color"]
        })
    parranda_cats_list.sort(key=lambda x: x["count"], reverse=True)

    # Top kalit so'zlar
    top_keywords = extract_top_keywords(responses, top_n=24)

    return {
        "total": total,
        "categories": categories_list,
        "top_keywords": top_keywords,
        "segment_counts": segment_counts,
        "chorva_stats": {
            "total": chorva_total,
            "categories": chorva_cats_list
        },
        "parranda_stats": {
            "total": parranda_total,
            "categories": parranda_cats_list
        },
        "cross_table": cross_table,
        "call_leads": call_leads
    }
