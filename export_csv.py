import sqlite3
import csv
from database import DB_NAME

OUTPUT_CSV = "custdev_javoblari.csv"

def export_to_csv():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                r.user_id, r.full_name, r.username, r.direction, r.livestock_count, 
                r.problem, r.problem_voice_path,
                r.solution_taken, r.solution_voice_path,
                r.dissatisfaction, r.dissatisfaction_voice_path,
                r.phone_number, ref.full_name, r.created_at
            FROM responses r
            LEFT JOIN responses ref ON r.referred_by = ref.user_id
            ORDER BY r.created_at DESC
        """)
        rows = cursor.fetchall()
        
        if not rows:
            print("Hozircha bazada hech qanday javob yo'q.")
            return

        headers = [
            "User ID", "Ism-familiya", "Username", "Yo'nalish (chorva/parranda)", 
            "Hajm (bosh soni)", "Muammo (2-savol)", "Muammo Ovozli Fayl",
            "Yechim & Xarajat (3-savol)", "Yechim Ovozli Fayl",
            "Yetishmagan jihat (4-savol)", "Yetishmagan Ovozli Fayl",
            "Telefon raqam", "Taklif qilgan (Referral)", "Vaqti"
        ]

        with open(OUTPUT_CSV, mode="w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

        print(f"✅ Muvaffaqiyatli eksport qilindi: {len(rows)} ta javob '{OUTPUT_CSV}' fayliga saqlandi!")
    except Exception as e:
        print(f"Xatolik yuz berdi: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    export_to_csv()
