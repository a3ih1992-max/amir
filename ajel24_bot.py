"""
بوت أخبار عاجل 24 - مراقبة متعددة المصادر 24/7
يستخدم Pillow مع معالجة صحيحة للنص العربي
"""

from PIL import Image, ImageDraw, ImageFont
import requests
import urllib.request
import xml.etree.ElementTree as ET
import os
import json
import time
import socket
import subprocess
import sys
from datetime import datetime

# ===================== تثبيت المكتبات =====================
def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    install("arabic-reshaper")
    install("python-bidi")
    import arabic_reshaper
    from bidi.algorithm import get_display

old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

# ===================== الإعدادات =====================
PAGE_HANDLE      = "Ajel24"
POSTER_SIZE      = (1080, 1080)
GROQ_API_KEY     = os.environ.get("GROQ_API_KEY", "")
CHECK_EVERY_MINUTES = 5
HISTORY_FILE     = "ajel24_history.json"
RED_COLOR        = (200, 30, 30)

# خط Cairo من Google Fonts
FONT_URL  = "https://github.com/google/fonts/raw/main/ofl/cairo/Cairo%5Bslnt%2Cwght%5D.ttf"
FONT_PATH = "Cairo.ttf"

# ===================== المصادر =====================
NEWS_SOURCES = [
    {"name": "الجزيرة",   "url": "https://www.aljazeera.net/rss"},
    {"name": "العربية",   "url": "https://www.alarabiya.net/tools/rss"},
    {"name": "سكاي نيوز", "url": "https://www.skynewsarabia.com/rss.xml"},
    {"name": "BBC عربي",  "url": "https://feeds.bbci.co.uk/arabic/rss.xml"},
    {"name": "فرانس 24",  "url": "https://www.france24.com/ar/rss"},
    {"name": "الميادين",  "url": "https://www.almayadeen.net/rss/news.xml"},
    {"name": "TRT عربي",  "url": "https://www.trtarabi.com/rss"},
    {"name": "الشرق",     "url": "https://asharq.com/feed/"},
    {"name": "CGTN عربي", "url": "https://arabic.cgtn.com/rss.xml"},
]

# ===================== تحميل الخط =====================
def download_font():
    if not os.path.exists(FONT_PATH):
        print("📥 تحميل الخط Cairo...")
        try:
            r = requests.get(FONT_URL, timeout=30)
            with open(FONT_PATH, "wb") as f:
                f.write(r.content)
            print("✅ تم تحميل الخط")
        except Exception as e:
            print(f"⚠️ فشل تحميل الخط: {e}")

# ===================== معالجة النص العربي =====================
def process_arabic(text):
    """
    الطريقة الوحيدة الصحيحة لعرض العربية في PIL:
    reshape أولاً لتوصيل الحروف، ثم get_display لعكس الاتجاه
    """
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except:
        return text

def split_to_lines(text, font, draw, max_width):
    """
    تقسيم النص إلى أسطر:
    - نعمل على النص الأصلي (غير المعالج)
    - نقيس كل سطر بعد المعالجة
    - نعيد القائمة معالجة
    """
    words = text.split()
    raw_lines = []
    current = []

    for word in words:
        current.append(word)
        # قياس السطر الحالي بعد المعالجة
        processed = process_arabic(" ".join(current))
        bbox = draw.textbbox((0, 0), processed, font=font)
        w = bbox[2] - bbox[0]
        if w > max_width and len(current) > 1:
            current.pop()
            raw_lines.append(" ".join(current))
            current = [word]

    if current:
        raw_lines.append(" ".join(current))

    # معالجة كل سطر
    return [process_arabic(line) for line in raw_lines]

# ===================== Groq =====================
def rephrase_with_groq(title):
    if not GROQ_API_KEY:
        return title
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        prompt = f"""أعد صياغة هذا العنوان الإخباري بأسلوب مختلف ومختصر:
"{title}"
- أسلوب صحفي عاجل
- أجب بالعنوان فقط بدون شرح"""

        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 100
        }
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers, json=body, timeout=15
        )
        data = resp.json()
        if "error" in data:
            return title
        new_title = data["choices"][0]["message"]["content"].strip().strip('"').strip("'")
        print(f"  ✏️ {new_title}")
        return new_title
    except Exception as e:
        print(f"  ⚠️ Groq: {e}")
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

# ===================== صنع البوستر =====================
def make_poster(title, source, output_path):
    W, H = POSTER_SIZE
    img  = Image.new("RGB", (W, H), color=RED_COLOR)
    draw = ImageDraw.Draw(img)

    try:
        f_badge  = ImageFont.truetype(FONT_PATH, 110)
        f_title  = ImageFont.truetype(FONT_PATH, 64)
        f_logo   = ImageFont.truetype(FONT_PATH, 72)
        f_source = ImageFont.truetype(FONT_PATH, 32)
        f_page   = ImageFont.truetype(FONT_PATH, 36)
    except Exception as e:
        print(f"⚠️ خطأ خط: {e}")
        return None

    # ── شارة عاجل ──
    badge = process_arabic("عاجل")
    bb = draw.textbbox((0, 0), badge, font=f_badge)
    bw, bh = bb[2]-bb[0], bb[3]-bb[1]
    bx = (W - bw - 100) // 2
    by = 100
    draw.rectangle([bx-6, by-6, bx+bw+106, by+bh+56], outline=(255,255,255), width=6)
    draw.text((bx+50-bb[0], by+25-bb[1]), badge, font=f_badge, fill=(255,255,255))

    # ── سهم ──
    ay = by + bh + 56
    draw.polygon([(W//2-22, ay),(W//2+22, ay),(W//2, ay+28)], fill=(255,255,255))

    # ── نص الخبر ──
    lines  = split_to_lines(title, f_title, draw, W - 140)
    lh     = 95
    total  = len(lines) * lh
    ty     = (H - total) // 2 + 40

    for i, line in enumerate(lines):
        bb = draw.textbbox((0,0), line, font=f_title)
        tw = bb[2]-bb[0]
        draw.text(((W-tw)//2 - bb[0], ty + i*lh - bb[1]), line, font=f_title, fill=(255,255,255))

    # ── المصدر ──
    src_txt = process_arabic(f"المصدر: {source}")
    bb = draw.textbbox((0,0), src_txt, font=f_source)
    sw = bb[2]-bb[0]
    draw.text(((W-sw)//2 - bb[0], ty+total+20 - bb[1]), src_txt, font=f_source, fill=(255,220,220))

    # ── الشعار ──
    logo = process_arabic("عاجل 24")
    bb = draw.textbbox((0,0), logo, font=f_logo)
    lw = bb[2]-bb[0]
    draw.text(((W-lw)//2 - bb[0], H-210 - bb[1]), logo, font=f_logo, fill=(255,255,255))
    draw.rectangle([(W//2)-100, H-128, (W//2)+100, H-124], fill=(255,255,255))

    # ── هاندل ──
    page = f"f  {PAGE_HANDLE}"
    bb = draw.textbbox((0,0), page, font=f_page)
    pw = bb[2]-bb[0]
    draw.text(((W-pw)//2, H-95), page, font=f_page, fill=(255,255,255))

    img.save(output_path, quality=95)
    print(f"  🖼️ {output_path}")
    return output_path

# ===================== جلب الأخبار =====================
def fetch_source(source):
    items = []
    try:
        req  = urllib.request.Request(source["url"], headers={"User-Agent":"Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        root = ET.fromstring(resp.read())
        for item in root.findall(".//item"):
            t = item.findtext("title","").strip()
            if t:
                items.append({"title":t, "source":source["name"]})
        print(f"  📡 {source['name']}: {len(items)}")
    except Exception as e:
        print(f"  ⚠️ {source['name']}: {e}")
    return items

def fetch_all():
    news = []
    for s in NEWS_SOURCES:
        news.extend(fetch_source(s))
        time.sleep(0.5)
    return news

# ===================== الفحص =====================
def check_once(history, counter):
    print(f"\n🔄 [{datetime.now().strftime('%H:%M:%S')}] فحص المصادر...")
    all_news = fetch_all()
    new_news = [n for n in all_news if n["title"] not in history]

    if not new_news:
        print(f"  ✅ لا جديد ({len(all_news)} خبر)")
        return history, counter

    print(f"  🔔 {len(new_news)} جديد!")
    for news in new_news:
        counter += 1
        title   = news["title"]
        source  = news["source"]
        print(f"\n  [{counter}] [{source}] {title[:60]}")
        new_title = rephrase_with_groq(title)
        make_poster(new_title, source, f"posters/ajel24_{counter:03d}.png")
        history = add_to_history(title, history)
        time.sleep(2)

    return history, counter

# ===================== Main =====================
if __name__ == "__main__":
    os.makedirs("posters", exist_ok=True)
    download_font()
    history = load_history()
    counter = len(history)

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        check_once(history, counter)
    else:
        print(f"🔴 عاجل 24 | {len(NEWS_SOURCES)} مصادر")
        while True:
            try:
                history, counter = check_once(history, counter)
                print(f"\n💤 {CHECK_EVERY_MINUTES} دقائق...")
                time.sleep(CHECK_EVERY_MINUTES * 60)
            except KeyboardInterrupt:
                print("\n⏹️ توقف")
                break
            except Exception as e:
                print(f"❌ {e}")
                time.sleep(60)
