# Fermamax - Fermerlar Klubi Telegram Boti 🌾

Instagramdan kelgan 25K+ auditoriya uchun CustDev (mijozlar muammolarini o'rganish) anketasi va yopiq guruhga 1 martalik taklif havolasi beruvchi bot.

---

## 🚀 Yangi 2 tarmoqli oqim (Chorva / Parranda)

1. **Boshlanish xabari (/start):**
   > Assalomu alaykum! 🌾 Fermerlar klubiga xush kelibsiz.
   > Guruhga kirishdan oldin atigi **4 ta qisqa savol**, 2 daqiqa. Javoblaringiz asosida sizga kerakli narsalarni tayyorlaymiz.
   >
   > **1-savol:** Qaysi yo'nalishda ishlaysiz?
   > `[🐄 Chorva]` `[🐔 Parranda]`

2. **🐄 "Chorva" tanlansa:**
   - **1-b:** Nechta bosh mol, qo'y yoki echkingiz bor? *(raqam yozsangiz kifoya)*
   - *Rahmat 🙏 Keyingi savol (2/4):*
   - **2-savol:** Oxirgi 1-2 oyda chorvangizda sizni eng ko'p qiynagan holat nima bo'ldi? Oxirgi marta qachon bo'lganini ham yozing. *(Masalan: mol kasal bo'ldi, sut kamaydi, em yoki pichan qimmat bo'ldi, mahsulotni sota olmadingiz)*
   - *Tushundim, rahmat 🙏 (3/4)*
   - **3-savol:** O'sha holatda nima qildingiz? Kimdan yordam so'radingiz (veterinar, qo'shni, internet) va taxminan qancha pul yoki vaqt ketdi?
   - *Juda foydali ma'lumot, rahmat! Oxirgi savol (4/4):*
   - **4-savol:** Qilgan yechimingiz to'liq yordam berdimi? Nima yetishmadi? Buni osonlashtirish uchun yana nima qidirgansiz yoki sinab ko'rgansiz?

3. **🐔 "Parranda" tanlansa:**
   - **1-b:** Nechta tovuq yoki boshqa parrandangiz bor? *(raqam yozsangiz kifoya)*
   - *Rahmat 🙏 Keyingi savol (2/4):*
   - **2-savol:** Oxirgi 1-2 oyda parrandachilikda sizni eng ko'p qiynagan holat nima bo'ldi? Oxirgi marta qachon bo'lganini ham yozing. *(Masalan: parranda kasal bo'ldi yoki nobud bo'ldi, em qimmat bo'ldi, tuxum yoki go'shtni sota olmadingiz, jo'ja topish qiyin bo'ldi)*
   - *Tushundim, rahmat 🙏 (3/4)*
   - **3-savol:** O'sha holatda nima qildingiz? Kimdan yordam so'radingiz (veterinar, em sotuvchi, qo'shni, internet) va taxminan qancha pul yoki vaqt ketdi?
   - *Juda foydali ma'lumot, rahmat! Oxirgi savol (4/4):*
   - **4-savol:** Qilgan yechimingiz to'liq yordam berdimi? Nima yetishmadi? Buni osonlashtirish uchun yana nima qidirgansiz yoki sinab ko'rgansiz?

4. **Yakuniy xabar & Havola:**
   - Guruhga 1 martalik link beriladi.
   - Ixtiyoriy: Telefon raqamini yuborish tugmasi (`[📱 Raqamni yuborish]` / `[➡️ O'tkazib yuborish]`).

5. **Ovozli xabarlar (Voice):** 2, 3 va 4-savollarda fermerlar ovozli xabar yuborishlari mumkin. Audiolar adminga alohida yetkaziladi.

---

## 🛠 O'rnatish va Sozlash

### 1. `.env` fayliga bot tokenini kiriting:
```env
BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
```

### 2. Guruh va Adminni avtomatik sozlash (`/id` buyrug'i):
1. Botni **Fermerlar Klubi** yopiq guruhiga qo'shing va **Admin** qiling (*Havola orqali taklif qilish* huquqini bering).
2. Guruh ichida `/id` deb yozing.
3. Bot guruhni va buyruqni yozgan sizni (adminni) avtomatik eslab qoladi!

## 🚀 24/7 To'xtovsiz Ishga Tushirish (Deploy)

Loyiha uchun `run.py` yaratildi. U **Telegram bot** va **Web Admin Panelni** bir vaqtning o'zida yagona jarayon sifatida ishga tushiradi.

### 1-usul: Oddiy Ubuntu VPS serverda (Systemd orqali — Tavsiya etiladi)
Eng arzon ($3–$5/oylik) VPS server yetarli (masalan: Hetzner, DigitalOcean, Timeweb, Vultr):

1. Serverga kiring va fayllarni yuklang:
   ```bash
   mkdir -p /var/www/fermamax
   cd /var/www/fermamax
   # Fayllarni yuklang
   ```
2. Virtual muhit va kutubxonalarni o'rnating:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Avtomatik qayta yoqilish (systemd) xizmatini yoqing:
   ```bash
   cp fermamax.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable fermamax
   sudo systemctl start fermamax
   ```
4. Holatini tekshirish:
   ```bash
   sudo systemctl status fermamax
   ```
*Endi server o'chib yonsa ham, yoki xatolik bo'lsa ham bot 5 soniyada avtomatik qayta ishlab ketadi!*

---

### 2-usul: Docker orqali (1 ta buyruq bilan)
Agar serveringizda Docker o'rnatilgan bo'lsa:
```bash
docker compose up -d --build
```
Loglarni ko'rish:
```bash
docker compose logs -f
```

---

### 3-usul: Mahally kompyuterda sinash:
```bash
source .venv/bin/activate
python3 run.py
```
Bir vaqtning o'zida ham bot, ham `http://localhost:8080` dagi admin panel ishlaydi.

---

## 👑 Admin Panel va CustDev Tahlil Tizimi

Admin panelga **avtomatik CustDev tahlil mexanizmi (Analytics Engine)** qo'shildi. U 10K+ javoblar ichidan:
1. **Eng ko'p uchrayotgan muammolar reytingi va foizlarini** (Em narxi, Kasalliklar, Veterinar topolmaslik, Bozor/sotish, Jo'ja/nasl) avtomatik hisoblaydi;
2. **"Kimlarda bu ko'proq uchrayapti?"** — Kichik, O'rta va Yirik xo'jaliklar bo'yicha qaysi muammo birinchi o'rinda turganini alohida ko'rsatib beradi;
3. **Intervyu (Deep CustDev) uchun ro'yxat:** Muammosi aniq bo'lib, telefon raqamini qoldirgan fermerlarni bitta tugma bilan filtrlash imkonini beradi.

---

### 1. Telegram ichidagi Admin Panel (`/admin`):
Telegram botingizga kiring va `/admin` deb yozing:
* 🔍 **Muammolar tahlili (CustDev):** Eng ko'p uchrayotgan muammolar foizi va segmentlar kesimidagi asosiy dardlarni Telegramda ko'rish;
* 📊 **Jonli statistika:** Jami anketalar, Chorva, Parranda, Telefon raqam qoldirganlar soni;
* 📋 **Oxirgi javoblarni ko'rish:** Fermerlarning javoblarini sahifalab o'qish;
* 📥 **Excel (CSV) yuklab olish:** Tugmani bosishingiz bilan `custdev_javoblari.csv` faylini yuboradi.

### 2. Brauzerdagi Web Admin Panel (`http://localhost:8080`):
Terminalda ishga tushiring:
```bash
python3 web_admin.py
```
Brauzerda oching: **`http://localhost:8080`**
* 📊 **Vizual Progress Barlar:** Har bir muammoning foizi va soni. Biron muammoni bossangiz — jadvalda faqat shu muammodan shikoyat qilgan fermerlar filtrlanaadi!
* 👥 **"Kimlarda bu ko'proq uchrayapti?" kartochkalari:** Kichik xo'jaliklarda nima asosiy muammo, yiriklarida nima asosiy ekanini ko'rsatadi.
* 📞 **"Faqat telefon qoldirganlar" tugmasi:** Qo'ng'iroq qilib, chuqur intervyu o'tkazish uchun tayyor kontaktlar filtri.

### 3. "Guruhga qo'shildi" xabarlarini avtomatik tozalash:
Bot guruhdagi *"X guruhga taklif havolasi orqali qo'shildi"* va *"X guruhdan chiqdi"* kabi barcha xizmat xabarlarini kelishi bilanoq avtomatik o'chiradi.
*(Eslatma: buning uchun botga guruh sozlamalarida **"Delete Messages" (Xabarlarni o'chirish)** huquqi berilgan bo'lishi kerak).*
