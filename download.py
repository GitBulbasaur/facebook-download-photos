#!/usr/bin/env python3
# Facebook Photo Downloader - STABLE
# Python 3.11+

import os
import re
import time
import argparse
import urllib.request
import hashlib
import sqlite3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm
from PIL import Image

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager


# ================= CONFIG =================

BASE_DIR = "photos"
MAX_WORKERS = 3
DOWNLOAD_RETRIES = 2
HASH_BLOCK = 1024 * 1024

# ========================================


# ---------------- Filesystem / DB ----------------

def ensure_dirs(username, album=None):
    base = os.path.join(BASE_DIR, username)
    os.makedirs(base, exist_ok=True)
    if album:
        os.makedirs(os.path.join(base, album), exist_ok=True)


def open_db(username):
    ensure_dirs(username)
    db = sqlite3.connect(os.path.join(BASE_DIR, username, ".index.db"))
    db.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            photo_id TEXT PRIMARY KEY,
            album TEXT,
            url TEXT,
            timestamp INTEGER,
            filename TEXT,
            sha256 TEXT
        )
    """)
    db.commit()
    return db


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(HASH_BLOCK):
            h.update(chunk)
    return h.hexdigest()


# ---------------- Browser ----------------

def create_browser():
    print("[*] Launching headless Chrome")
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=opts
    )
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
    )
    return driver


def wait_ready(d, t=15):
    WebDriverWait(d, t).until(
        lambda x: x.execute_script("return document.readyState") == "complete"
    )


def extract_photo_id(url):
    m = re.search(r"fbid=(\d+)", url)
    return m.group(1) if m else None


def extract_created_time(driver):
    """
    Extracts photo creation timestamp from page source.
    Falls back gracefully.
    """
    m = re.search(r'"created_time":(\d+)', driver.page_source)
    return int(m.group(1)) if m else int(time.time())


# ---------------- Phase 1: collect FBIDs ----------------

def collect_photo_ids(driver, username, album):
    print(f"    [+] Collecting photo IDs ({album})")
    driver.get(f"https://www.facebook.com/{username}/photos_{album}")
    wait_ready(driver)
    time.sleep(3)

    ids = set()
    last = 0

    for _ in range(50):
        thumbs = driver.find_elements(By.XPATH, "//a[contains(@href,'fbid=')]")
        for t in thumbs:
            pid = extract_photo_id(t.get_attribute("href"))
            if pid:
                ids.add(pid)

        if len(ids) == last:
            break
        last = len(ids)

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)

    print(f"    [+] Found {len(ids)} photos")
    return sorted(ids)


# ---------------- Phase 2: index photos ----------------

def index_album(driver, db, username, album):
    print(f"[*] Indexing album: {username}/{album}")
    ensure_dirs(username, album)

    photo_ids = collect_photo_ids(driver, username, album)
    if not photo_ids:
        print(f"    [!] No photos found")
        return 0

    indexed = 0

    with tqdm(photo_ids, desc=f"Indexing {album}", unit="photo") as bar:
        for pid in bar:
            url = f"https://www.facebook.com/photo/?fbid={pid}"
            driver.get(url)
            wait_ready(driver)
            time.sleep(1)

            imgs = driver.find_elements(By.XPATH, "//img[contains(@src,'scontent')]")
            if not imgs:
                continue

            img = max(
                imgs,
                key=lambda i: i.size.get("width", 0) * i.size.get("height", 0)
            )
            img_url = img.get_attribute("src")

            ts = extract_created_time(driver)
            date_str = datetime.utcfromtimestamp(ts).strftime("%Y%m%d")
            filename = f"{date_str}_fb_{album}_{username}_{pid}.jpg"

            db.execute("""
                INSERT OR IGNORE INTO photos
                (photo_id, album, url, timestamp, filename, sha256)
                VALUES (?, ?, ?, ?, ?, NULL)
            """, (pid, album, img_url, ts, filename))
            db.commit()
            indexed += 1

    print(f"    [+] Indexed {indexed} photos")
    return indexed


# ---------------- Download ----------------

def download_worker(username, row):
    pid, album, url, ts, filename, sha = row
    path = os.path.join(BASE_DIR, username, album, filename)

    if os.path.exists(path) and sha and sha256_file(path) == sha:
        return "skip", None

    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            urllib.request.urlretrieve(url, path)
            if os.path.getsize(path) > 0:
                os.utime(path, (ts, ts))
                return "ok", sha256_file(path)
        except Exception:
            time.sleep(attempt)

    return "fail", None


# ---------------- Main ----------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("-e", "--email", required=True)
    p.add_argument("-p", "--password", required=True)
    p.add_argument("-u", "--username")
    p.add_argument("--users-file")
    p.add_argument("--index-only", action="store_true")
    p.add_argument("--download-only", action="store_true")
    args = p.parse_args()

    # Resolve users
    if args.users_file:
        with open(args.users_file) as f:
            users = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    else:
        users = [args.username]

    driver = None
    if not args.download_only:
        driver = create_browser()
        print("[*] Logging into Facebook")
        driver.get("https://www.facebook.com/login")
        wait_ready(driver)

        driver.find_element(By.ID, "email").send_keys(args.email)
        driver.find_element(By.ID, "pass").send_keys(args.password)
        driver.find_element(By.NAME, "login").click()
        time.sleep(5)

    for user in users:
        print(f"\n=== USER: {user} ===")
        db = open_db(user)

        if not args.download_only:
            total_indexed = 0
            for album in ("of", "by"):
                total_indexed += index_album(driver, db, user, album)
            print(f"[SUMMARY] Indexed {total_indexed} photos for {user}")

        if not args.index_only:
            rows = db.execute(
                "SELECT photo_id, album, url, timestamp, filename, sha256 FROM photos"
            ).fetchall()

            if not rows:
                print("[!] No photos to download")
            else:
                ok = skip = fail = 0
                with ThreadPoolExecutor(MAX_WORKERS) as ex:
                    futures = {
                        ex.submit(download_worker, user, r): r for r in rows
                    }
                    for f in tqdm(as_completed(futures), total=len(futures), desc="Downloading"):
                        status, h = f.result()
                        pid = futures[f][0]

                        if status == "ok":
                            ok += 1
                            db.execute(
                                "UPDATE photos SET sha256=? WHERE photo_id=?",
                                (h, pid)
                            )
                            db.commit()
                        elif status == "skip":
                            skip += 1
                        else:
                            fail += 1

                print("[DOWNLOAD SUMMARY]")
                print(f"  Downloaded : {ok}")
                print(f"  Skipped    : {skip}")
                print(f"  Failed     : {fail}")

        db.close()

    if driver:
        driver.quit()

    print("\nAll tasks completed successfully.")


if __name__ == "__main__":
    main()
