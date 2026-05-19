"""
بوت أخبار عاجل 24 - مراقبة الجزيرة 24/7
"""

from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import requests
import urllib.request
import xml.etree.ElementTree as ET
import os
import json
import time
import socket
from datetime import datetime

old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

# ===================== الإعدادات =====================
PAGE_NAME        = "عاجل 24"
PAGE_HANDLE      = "Ajel24"
POSTER_SIZE      = (1080, 1080)

GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")

CHECK_EVERY_MINUTES = 5
HISTORY_FILE        = "ajel24_history.json"

ARABIC_FONT_PATH = "Amiri-Bold.ttf"

ALJAZEERA_RSS = "https://www.aljazeera.net/rss"
SOURCE_NAME   = "الجزيرة"

RED_COLOR = (200, 30, 30)

# ===================== Groq =====================

def rephrase_with_groq(title):
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        prompt = f"""أعد صياغة هذا العنوان الإخباري بأسلوب مختلف ومختصر مع الحفاظ على المعنى الكامل:
"{title}"

شروط:
- لا تستخدم نفس الكلمات الأصلية كلها
- اجعله أقصر إن أمكن
- استخدم أسلوب صحفي عاجل
- أجب بالعنوان الجديد فقط بدون أي شرح أو علامات اقتباس"""

        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 100
        }
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        data = resp.json()

        if "error" in data:
            print(f"  ⚠️ Groq error: {data['error'].get('message', '')}")
            return title

        new_title = data["choices"][0]["message"]["content"].strip()
        new_title = new_title.strip('"').strip("'").strip()
        print(f"  ✏️ صياغة جديدة: {new_title}")
        return new_title

    except Exception as e:
        print(f"  ⚠️ خطأ Groq: {e}")
        return title

# ===================== سجل الأخبار =====================

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def add_to_history(title, history):
    history.append(title)
    if len(history) > 2000:
        history = history[-2000:]
    save_history(history)
    return history

# ===================== ✅ دالة النص الصحيحة =====================

def ar(text):
    """تحويل النص العربي للعرض الصحيح في PIL"""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

def wrap_text(text, font, draw, max_width):
    """تقسيم النص إلى أسطر بناءً على عرض الصورة"""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        current_line.append(word)
        test_line = " ".join(current_line)
        test_display = ar(test_line)
        bbox = draw.textbbox((0, 0), test_display, font=font)
        w = bbox[2] - bbox[0]
        if w > max_width and len(current_line) > 1:
            current_line.pop()
            lines.append(ar(" ".join(current_line)))
            current_line = [word]

    if current_line:
        lines.append(ar(" ".join(current_line)))

    return lines

# ===================== صنع البوستر =====================

def make_breaking_poster(title, source, output_path="poster.png"):
    W, H = POSTER_SIZE
    result = Image.new("RGB", (W, H), color=RED_COLOR)
    draw = ImageDraw.Draw(result)

    try:
        font_badge  = ImageFont.truetype(ARABIC_FONT_PATH, 110)
        font_title  = ImageFont.truetype(ARABIC_FONT_PATH, 62)
        font_logo   = ImageFont.truetype(ARABIC_FONT_PATH, 70)
        font_page   = ImageFont.truetype(ARABIC_FONT_PATH, 36)
        font_source = ImageFont.truetype(ARABIC_FONT_PATH, 30)
    except Exception as e:
        print(f"⚠️ خطأ في الخط: {e}")
        return None

    # ===== شارة "عاجل" =====
    badge_text = ar("عاجل")
    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    bw = bbox[2] - bbox[0]
    bh = bbox[3] - bbox[1]
    box_w = bw + 100
    box_h = bh + 50
    box_x = (W - box_w) // 2
    box_y = 100

    draw.rectangle(
        [box_x - 6, box_y - 6, box_x + box_w + 6, box_y + box_h + 6],
        outline=(255, 255, 255), width=6
    )
    text_x = box_x + (box_w - bw) // 2 - bbox[0]
    text_y = box_y + (box_h - bh) // 2 - bbox[1]
    draw.text((text_x, text_y), badge_text, font=font_badge, fill=(255, 255, 255))

    # السهم
    arrow_y = box_y + box_h + 6
    arrow_points = [
        (W // 2 - 22, arrow_y),
        (W // 2 + 22, arrow_y),
        (W // 2, arrow_y + 28)
    ]
    draw.polygon(arrow_points, fill=(255, 255, 255))

    # ===== نص الخبر =====
    max_text_width = W - 120
    lines = wrap_text(title, font_title, draw, max_text_width)

    line_h = 90
    total_text_h = len(lines) * line_h
    text_start_y = (H - total_text_h) // 2 + 50

    for i, line in enumerate(lines):
        y = text_start_y + i * line_h
        bbox = draw.textbbox((0, 0), line, font=font_title)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        draw.text((x, y), line, font=font_title, fill=(255, 255, 255))

    # ===== المصدر =====
    source_text = ar(f"المصدر: {source}")
    bbox = draw.textbbox((0, 0), source_text, font=font_source)
    sw = bbox[2] - bbox[0]
    source_y = text_start_y + total_text_h + 25
    draw.text(((W - sw) // 2, source_y), source_text, font=font_source, fill=(255, 220, 220))

    # ===== الشعار =====
    logo_text = ar("عاجل 24")
    bbox = draw.textbbox((0, 0), logo_text, font=font_logo)
    lw = bbox[2] - bbox[0]
    draw.text(((W - lw) // 2, H - 200), logo_text, font=font_logo, fill=(255, 255, 255))

    draw.rectangle([(W // 2) - 100, H - 125, (W // 2) + 100, H - 121], fill=(255, 255, 255))

    page_text = f"f  {PAGE_HANDLE}"
    bbox = draw.textbbox((0, 0), page_text, font=font_page)
    pw = bbox[2] - bbox[0]
    draw.text(((W - pw) // 2, H - 95), page_text, font=font_page, fill=(255, 255, 255))

    result.save(output_path, quality=95)
    print(f"  🖼️ تم حفظ: {output_path}")
    return output_path

# ===================== جلب الأخبار =====================

def fetch_news():
    news_list = []
    try:
        req = urllib.request.Request(ALJAZEERA_RSS, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        root = ET.fromstring(resp.read())
        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            link  = item.findtext("link", "").strip()
            if title:
                news_list.append({"title": title, "link": link})
    except Exception as e:
        print(f"❌ خطأ في جلب الأخبار: {e}")
    return news_list

# ===================== الفحص الواحد =====================

def check_once(history, counter):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n🔄 [{now}] فحص الجزيرة...")

    all_news = fetch_news()
    if not all_news:
        print("  ⚠️ لا توجد أخبار")
        return history, counter

    new_news = [n for n in all_news if n["title"] not in history]

    if not new_news:
        print(f"  ✅ لا أخبار جديدة (آخر فحص: {len(all_news)} خبر)")
        return history, counter

    print(f"  🔔 {len(new_news)} خبر جديد!")

    for news in new_news:
        title = news["title"]
        counter += 1
        print(f"\n  📌 [{counter}] {title[:70]}")

        new_title = rephrase_with_groq(title)

        output = f"posters/ajel24_{counter:03d}.png"
        make_breaking_poster(new_title, SOURCE_NAME, output_path=output)
        print(f"  ✅ بوستر جاهز: {output}")

        history = add_to_history(title, history)
        time.sleep(2)

    return history, counter

# ===================== التشغيل الدائم =====================

def run_forever():
    print(f"\n{'='*55}")
    print(f"🔴 عاجل 24 — وضع المراقبة الدائمة 24/7")
    print(f"📡 المصدر: الجزيرة")
    print(f"⏰ يفحص كل {CHECK_EVERY_MINUTES} دقائق")
    print(f"{'='*55}\n")

    os.makedirs("posters", exist_ok=True)
    history = load_history()
    counter = len(history)

    while True:
        try:
            history, counter = check_once(history, counter)
            print(f"\n💤 انتظار {CHECK_EVERY_MINUTES} دقائق...")
            time.sleep(CHECK_EVERY_MINUTES * 60)
        except KeyboardInterrupt:
            print("\n\n⏹️ تم إيقاف البوت")
            break
        except Exception as e:
            print(f"\n❌ خطأ غير متوقع: {e}")
            time.sleep(60)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        os.makedirs("posters", exist_ok=True)
        history = load_history()
        counter = len(history)
        check_once(history, counter)
    else:
        run_forever()
