"""
بوت أخبار عاجل 24
ينشر بوستراً واحداً في كل تشغيل
"""

import requests
import urllib.request
import xml.etree.ElementTree as ET
import os
import json
import time
import socket
import sys
import subprocess
from datetime import datetime

old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

# ===================== الإعدادات =====================
PAGE_HANDLE         = "Ajel24"
GROQ_API_KEY        = os.environ.get("GROQ_API_KEY", "")
CHECK_EVERY_MINUTES = 15
HISTORY_FILE        = "ajel24_history.json"
LATEST_FILE         = "latest.txt"
MAX_POSTERS         = 100
GITHUB_RAW          = "https://raw.githubusercontent.com/a3ih1992-max/amir/main/posters/"

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

POLITICAL_KEYWORDS = [
    "رئيس", "وزير", "حكومة", "برلمان", "انتخاب", "سفير", "دبلوماسي",
    "مجلس", "قمة", "اتفاق", "معاهدة", "تحالف", "حزب", "زعيم",
    "أمين عام", "أمم متحدة", "مجلس الأمن", "ناتو", "اتحاد أوروبي",
    "سياسة", "دولة", "حرب", "صراع", "أزمة", "مفاوضات", "وقف إطلاق",
    "هجوم", "قصف", "غارة", "عملية عسكرية", "جيش", "قوات",
    "اقتصاد", "عقوبات", "نفط", "غاز", "اتفاقية", "ميثاق",
    "ترامب", "بوتين", "بايدن", "نتنياهو", "ماكرون", "شي جين",
    "إسرائيل", "فلسطين", "غزة", "لبنان", "سوريا", "إيران", "العراق",
    "اليمن", "السودان", "ليبيا", "أوكرانيا", "روسيا", "الصين",
    "أمريكا", "الولايات المتحدة", "أوروبا", "الخليج", "السعودية"
]

def is_political(title):
    for keyword in POLITICAL_KEYWORDS:
        if keyword in title:
            return True
    return False

# ===================== حذف البوسترات القديمة =====================
def cleanup_old_posters():
    try:
        folder = "posters"
        files = sorted([f for f in os.listdir(folder) if f.endswith(".png")])
        if len(files) > MAX_POSTERS:
            to_delete = files[:len(files) - MAX_POSTERS]
            for f in to_delete:
                png_path = os.path.join(folder, f)
                txt_path = png_path.replace(".png", ".txt")
                os.remove(png_path)
                if os.path.exists(txt_path):
                    os.remove(txt_path)
            print(f"  🗑️ تم حذف {len(to_delete)} بوستر قديم")
    except Exception as e:
        print(f"  ⚠️ خطأ في الحذف: {e}")

# ===================== تحديث latest.txt =====================
def update_latest(poster_name):
    with open(LATEST_FILE, "w", encoding="utf-8") as f:
        f.write(GITHUB_RAW + poster_name)
    print(f"  📝 latest.txt → {poster_name}")

# ===================== تثبيت Playwright =====================
def setup_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "-q"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        return True

# ===================== HTML البوستر =====================
def build_html(title, source):
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: 1080px; height: 1080px;
    background: #c81e1e;
    display: flex; flex-direction: column;
    align-items: center; justify-content: flex-start;
    font-family: 'Amiri', serif; direction: rtl; overflow: hidden;
  }}
  .badge-wrap {{ display: flex; flex-direction: column; align-items: center; margin-top: 90px; }}
  .badge {{ border: 7px solid white; padding: 16px 80px; font-size: 100px; font-weight: 700; color: white; line-height: 1.1; background: #c81e1e; }}
  .arrow {{ width: 0; height: 0; border-left: 28px solid transparent; border-right: 28px solid transparent; border-top: 36px solid white; }}
  .content {{ margin-top: 60px; padding: 0 70px; text-align: center; width: 100%; flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; }}
  .title {{ font-size: 74px; font-weight: 700; color: white; line-height: 1.65; direction: rtl; text-align: center; }}
  .source {{ font-size: 34px; font-weight: 400; color: rgba(255,220,220,0.85); margin-top: 40px; }}
  .footer {{ width: 100%; text-align: center; padding-bottom: 60px; }}
  .footer-line {{ width: 220px; height: 3px; background: rgba(255,255,255,0.5); margin: 0 auto 20px; }}
  .logo {{ font-size: 80px; font-weight: 700; color: white; display: block; line-height: 1.1; }}
  .handle {{ font-size: 32px; color: rgba(255,255,255,0.7); margin-top: 10px; display: block; }}
</style>
</head>
<body>
  <div class="badge-wrap">
    <div class="badge">خبر</div>
    <div class="arrow"></div>
  </div>
  <div class="content">
    <div class="title">{title}</div>
    <div class="source">المصدر: {source}</div>
  </div>
  <div class="footer">
    <div class="footer-line"></div>
    <span class="logo">عاجل 24</span>
    <span class="handle">f &nbsp; {PAGE_HANDLE}</span>
  </div>
</body>
</html>"""

# ===================== صنع البوستر =====================
def make_poster(title, source, output_path):
    try:
        from playwright.sync_api import sync_playwright
        html = build_html(title, source)
        html_file = output_path.replace(".png", ".html")
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1080, "height": 1080})
            page.goto(f"file://{os.path.abspath(html_file)}")
            page.wait_for_timeout(3000)
            page.screenshot(path=output_path, full_page=False)
            browser.close()
        os.remove(html_file)
        print(f"  🖼️ {output_path}")
        return output_path
    except Exception as e:
        print(f"  ❌ خطأ في البوستر: {e}")
        return None

# ===================== Groq =====================
def rephrase_with_groq(title):
    if not GROQ_API_KEY:
        return title
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": f'أعد صياغة هذا العنوان الإخباري بأسلوب مختصر واضح:\n"{title}"\nأجب بالعنوان فقط بدون شرح.'}],
            "temperature": 0.7, "max_tokens": 100
        }
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=body, timeout=15)
        data = resp.json()
        if "error" in data:
            return title
        return data["choices"][0]["message"]["content"].strip().strip('"').strip("'")
    except:
        return title

def generate_caption(title, source):
    if not GROQ_API_KEY:
        return f"📰 {title}\n\nالمصدر: {source}\n\n#عاجل24 #أخبار"
    try:
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": f'اكتب نصاً مختصراً لمنشور فيسبوك عن هذا الخبر:\n"{title}"\nالمصدر: {source}\nالشروط:\n- 3 أسطر فقط\n- السطر الأول: ملخص الخبر\n- السطر الثاني: تفاصيل مختصرة\n- السطر الثالث: هاشتاقات عربية\n- لا تضع مقدمة، فقط النص مباشرة'}],
            "temperature": 0.7, "max_tokens": 200
        }
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=body, timeout=15)
        data = resp.json()
        if "error" in data:
            return f"📰 {title}\n\nالمصدر: {source}\n\n#عاجل24 #أخبار"
        caption = data["choices"][0]["message"]["content"].strip()
        caption += f"\n\n🔴 عاجل 24 | f {PAGE_HANDLE}"
        return caption
    except:
        return f"📰 {title}\n\nالمصدر: {source}\n\n#عاجل24 #أخبار"

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

# ===================== جلب الأخبار =====================
def fetch_source(source):
    items = []
    try:
        req  = urllib.request.Request(source["url"], headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        root = ET.fromstring(resp.read())
        for item in root.findall(".//item"):
            t = item.findtext("title", "").strip()
            if t and is_political(t):
                items.append({"title": t, "source": source["name"]})
        print(f"  📡 {source['name']}: {len(items)} خبر سياسي")
    except Exception as e:
        print(f"  ⚠️ {source['name']}: {e}")
    return items

def fetch_all():
    news = []
    for s in NEWS_SOURCES:
        news.extend(fetch_source(s))
        time.sleep(0.5)
    return news

# ===================== الفحص — بوستر واحد فقط =====================
def check_once(history, counter):
    print(f"\n🔄 [{datetime.now().strftime('%H:%M:%S')}] فحص المصادر...")
    cleanup_old_posters()

    all_news = fetch_all()
    new_news = [n for n in all_news if n["title"] not in history]

    if not new_news:
        print(f"  ✅ لا جديد ({len(all_news)} خبر)")
        return history, counter

    # خذ أول خبر جديد فقط
    news   = new_news[0]
    counter += 1
    title  = news["title"]
    source = news["source"]
    print(f"\n  [{counter}] [{source}] {title[:60]}")

    new_title   = rephrase_with_groq(title)
    poster_name = f"ajel24_{counter:03d}.png"
    poster_path = f"posters/{poster_name}"

    make_poster(new_title, source, poster_path)
    caption = generate_caption(new_title, source)

    txt_path = poster_path.replace(".png", ".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(caption)

    update_latest(poster_name)
    history = add_to_history(title, history)

    return history, counter

# ===================== Main =====================
if __name__ == "__main__":
    os.makedirs("posters", exist_ok=True)
    setup_playwright()
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
