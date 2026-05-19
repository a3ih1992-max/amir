"""
بوت أخبار عاجل 24
يستخدم HTML + Playwright لرسم البوسترات بنص عربي صحيح 100%
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
CHECK_EVERY_MINUTES = 5
HISTORY_FILE        = "ajel24_history.json"

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

# ===================== تثبيت Playwright =====================
def setup_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        print("📥 تثبيت Playwright...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "-q"])
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
        return True

# ===================== إنشاء HTML للبوستر =====================
def build_html(title, source):
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Cairo:wght@700;900&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: 1080px;
    height: 1080px;
    background: #c81e1e;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    font-family: 'Amiri', 'Cairo', Arial, sans-serif;
    direction: rtl;
    overflow: hidden;
  }}
  .badge-wrap {{
    display: flex;
    flex-direction: column;
    align-items: center;
    position: absolute;
    top: 100px;
  }}
  .badge {{
    border: 6px solid white;
    padding: 18px 55px;
    font-size: 110px;
    font-weight: 700;
    color: white;
    letter-spacing: 4px;
    line-height: 1.1;
    font-family: 'Amiri', serif;
  }}
  .arrow {{
    width: 0;
    height: 0;
    border-left: 22px solid transparent;
    border-right: 22px solid transparent;
    border-top: 28px solid white;
  }}
  .content {{
    margin-top: 320px;
    padding: 0 60px;
    text-align: center;
    width: 100%;
  }}
  .title {{
    font-size: 72px;
    font-weight: 700;
    color: white;
    line-height: 1.6;
    margin-bottom: 30px;
    direction: rtl;
    font-family: 'Amiri', serif;
  }}
  .source {{
    font-size: 32px;
    color: rgba(255,220,220,0.9);
    margin-top: 20px;
    font-family: 'Amiri', serif;
  }}
  .footer {{
    position: absolute;
    bottom: 80px;
    text-align: center;
    width: 100%;
  }}
  .logo {{
    font-size: 72px;
    font-weight: 700;
    color: white;
    display: block;
    margin-bottom: 10px;
    font-family: 'Amiri', serif;
  }}
  .line {{
    width: 200px;
    height: 4px;
    background: white;
    margin: 10px auto;
  }}
  .handle {{
    font-size: 36px;
    color: white;
    font-family: 'Cairo', sans-serif;
  }}
</style>
</head>
<body>
  <div class="badge-wrap">
    <div class="badge">عاجل</div>
    <div class="arrow"></div>
  </div>
  <div class="content">
    <div class="title">{title}</div>
    <div class="source">المصدر: {source}</div>
  </div>
  <div class="footer">
    <span class="logo">عاجل 24</span>
    <div class="line"></div>
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
            page.wait_for_timeout(2000)  # انتظار تحميل خط Amiri
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
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        body = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": f"""أعد صياغة هذا العنوان الإخباري بأسلوب عاجل مختصر:
"{title}"
أجب بالعنوان فقط بدون شرح."""}],
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
    except:
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

# ===================== جلب الأخبار =====================
def fetch_source(source):
    items = []
    try:
        req  = urllib.request.Request(source["url"], headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        root = ET.fromstring(resp.read())
        for item in root.findall(".//item"):
            t = item.findtext("title", "").strip()
            if t:
                items.append({"title": t, "source": source["name"]})
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
        title  = news["title"]
        source = news["source"]
        print(f"\n  [{counter}] [{source}] {title[:60]}")
        new_title = rephrase_with_groq(title)
        make_poster(new_title, source, f"posters/ajel24_{counter:03d}.png")
        history = add_to_history(title, history)
        time.sleep(2)

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
