from flask import Flask, render_template, request, jsonify
import requests
import time
import re
import os
import json
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "dz-boost-secret-2025"

INSTAGRAM_URL = "https://www.instagram.com/_u.wej"
TELEGRAM_CHANNEL = "https://t.me/mrnsk0"

TELEGRAM_BOT_TOKEN = os.environ.get("8673429842:AAEg7-3Uqe4NGzY-pw-Tdx96-7DhttuoYLo", "")
TELEGRAM_CHAT_ID = os.environ.get("7061266013", "")

COOLDOWN_FILE = "cooldowns.json"
COOLDOWN_HOURS = 24


@app.context_processor
def inject_globals():
    return {
        "instagram_url": INSTAGRAM_URL,
        "telegram_channel": TELEGRAM_CHANNEL,
    }


def load_cooldowns():
    if os.path.exists(COOLDOWN_FILE):
        try:
            with open(COOLDOWN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cooldowns(data):
    try:
        with open(COOLDOWN_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Save error: {e}")


def check_cooldown(username):
    cooldowns = load_cooldowns()
    key = username.lower()
    if key in cooldowns:
        last_order = datetime.fromisoformat(cooldowns[key])
        elapsed = datetime.now() - last_order
        remaining = timedelta(hours=COOLDOWN_HOURS) - elapsed
        if remaining.total_seconds() > 0:
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            return True, f"{hours} ساعة و {minutes} دقيقة"
    return False, ""


def set_cooldown(username):
    cooldowns = load_cooldowns()
    cooldowns[username.lower()] = datetime.now().isoformat()
    save_cooldowns(cooldowns)


def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials not set!")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/order")
def order():
    return render_template("order.html")


@app.route("/api/order", methods=["POST"])
def api_order():
    username = request.form.get("username", "").strip().lstrip("@")
    service = request.form.get("service", "").strip()
    quantity = request.form.get("quantity", "").strip()
    notes = request.form.get("notes", "").strip()

    if not username:
        return jsonify({"status": "error", "message": "الرجاء إدخال اسم المستخدم"}), 400

    if not re.match(r'^[a-zA-Z0-9._]{1,30}$', username):
        return jsonify({"status": "error", "message": "اسم المستخدم غير صالح"}), 400

    if not service:
        return jsonify({"status": "error", "message": "الرجاء اختيار الخدمة"}), 400

    if not quantity or not quantity.isdigit():
        return jsonify({"status": "error", "message": "الكمية غير صالحة"}), 400

    qty = int(quantity)

    # 🔥 الخدمات مع الحدود اليومية
    services_map = {
        "followers": {
            "name": "📸 متابعين إنستغرام",
            "min": 10,
            "max": 50,
        },
        "views": {
            "name": "👁️ مشاهدات ريلز",
            "min": 100,
            "max": 500,
        },
        "likes": {
            "name": "❤️ إعجابات",
            "min": 50,
            "max": 300,
        },
    }

    if service not in services_map:
        return jsonify({"status": "error", "message": "خدمة غير معروفة"}), 400

    svc = services_map[service]
    if qty < svc["min"] or qty > svc["max"]:
        return jsonify({
            "status": "error",
            "message": f"الكمية يجب أن تكون بين {svc['min']} و {svc['max']}"
        }), 400

    # 🔥 التحقق من الحظر (24 ساعة)
    is_blocked, remaining = check_cooldown(username)
    if is_blocked:
        return jsonify({
            "status": "error",
            "message": f"⏳ لقد طلبت بالفعل. يمكنك الطلب مجدداً بعد {remaining}."
        }), 429

    service_name = svc["name"]
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    message = f"""
🔔 <b>طلب جديد على Dz Boost</b>

━━━━━━━━━━━━━━━━
👤 <b>الحساب:</b> @{username}
🎯 <b>الخدمة:</b> {service_name}
📊 <b>الكمية:</b> {qty}
━━━━━━━━━━━━━━━━
🕐 <b>الوقت:</b> {now}
"""

    if notes:
        message += f"\n📝 <b>ملاحظات:</b>\n{notes}\n"

    message += "\n✅ يرجى تنفيذ الطلب في أقرب وقت."

    ok = send_telegram(message)

    if ok:
        set_cooldown(username)
        return jsonify({
            "status": "ok",
            "message": f"تم إرسال طلبك بنجاح! سيتم تنفيذه قريباً.\nيمكنك الطلب مجدداً بعد {COOLDOWN_HOURS} ساعة.",
        })
    else:
        return jsonify({
            "status": "error",
            "message": "فشل إرسال الطلب، حاول مرة أخرى"
        }), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
