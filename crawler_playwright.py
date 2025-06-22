
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import csv
import os
from playwright.sync_api import sync_playwright

domains = []
seen_phones = set()
with open("firmy.csv", newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    firms = []
    counter = 0
    for row in reader:
        name = row.get("nazwa", "").strip()
        phone = row.get("telefon", "").strip()
        website = row.get("strona", "").strip()

        if not website or "facebook.com" in website.lower() or phone in seen_phones:
            continue
        seen_phones.add(phone)

        firms.append({"name": name, "phone": phone, "website": website})
        domains.append(website)

IGNORED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".doc", ".docx", ".zip", ".rar", ".mp4", ".mp3"]
visited = set()

def is_valid_link(link, base_domain):
    if any(link.lower().endswith(ext) for ext in IGNORED_EXTENSIONS):
        return False
    if not link.startswith("http"):
        return True
    return urlparse(link).netloc == urlparse(base_domain).netloc

def extract_first_email(text):
    match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}", text)
    return match.group(0) if match else None

def extract_mailto_email(soup):
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            email = href.replace("mailto:", "").split("?")[0]
            if re.match(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}", email):
                return email
    return None

def extract_email_from_scripts(soup):
    scripts = soup.find_all(["script", "style"])
    for s in scripts:
        found = extract_first_email(s.get_text())
        if found:
            return found
    jsons = soup.find_all("script", type="application/ld+json")
    for s in jsons:
        found = extract_first_email(s.get_text())
        if found:
            return found
    return None

async def crawl_website(domain, page):
    visited.clear()
    priority_links = []
    other_links = []

    try:
        print(f"🔍 [1] Strona główna: {domain}")
        await page.goto(domain, timeout=30000, wait_until="networkidle")
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")
        email = extract_first_email(soup.get_text()) or extract_mailto_email(soup) or extract_email_from_scripts(soup)
        if email:
            print(f"✅ Mail na stronie głównej: {email}")
            return email

        for a in soup.find_all("a", href=True):
            link = urljoin(domain, a["href"])
            if not is_valid_link(link, domain):
                continue
            if link in visited:
                continue
            visited.add(link)
            if any(x in link.lower() for x in ["kontakt", "contact"]):
                priority_links.append(link)
            else:
                other_links.append(link)

    except Exception as e:
        print(f"⚠️ Błąd przy stronie głównej {domain}: {e}")

    for url in priority_links[:10]:
        try:
            print(f"📌 [2] Podstrona kontaktowa: {url}")
            page.goto(url, timeout=10000)
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            email = extract_first_email(soup.get_text()) or extract_mailto_email(soup) or extract_email_from_scripts(soup)
            if email:
                print(f"✅ Mail na podstronie kontaktowej: {email}")
                return email
        except Exception as e:
            print(f"⚠️ Błąd przy {url}: {e}")
            continue

    for url in other_links[:10]:
        try:
            print(f"🌐 [3] Inna podstrona: {url}")
            page.goto(url, timeout=10000)
            html = page.content()
            soup = BeautifulSoup(html, "html.parser")
            email = extract_first_email(soup.get_text()) or extract_mailto_email(soup) or extract_email_from_scripts(soup)
            if email:
                print(f"✅ Mail na zwykłej podstronie: {email}")
                return email
        except Exception as e:
            print(f"⚠️ Błąd przy {url}: {e}")
            continue

    print("❌ Brak maila w całej domenie.")
    return None

output_path = os.path.join(os.path.expanduser("~"), "Desktop", "maile.csv")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Domena", "Email"])

        for domain in domains:
            email = crawl_website(domain, page)
            writer.writerow([domain, email if email else "Brak maila"])

    browser.close()

print(f"✅ GOTOWE! Zapisano do pliku: {output_path}")
