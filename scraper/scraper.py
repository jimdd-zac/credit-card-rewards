#!/usr/bin/env python3
"""
台灣信用卡優惠爬蟲程式
從 Money101 等比較平台抓取最新信用卡海外消費回饋資訊
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("需要安裝依賴套件，請執行：")
    print("  pip install requests beautifulsoup4")
    sys.exit(1)

DATA_DIR = Path(__file__).parent.parent / "data"
CARDS_FILE = DATA_DIR / "cards.json"
REWARDS_FILE = DATA_DIR / "rewards.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


def fetch_money101_overseas_cards():
    """從 Money101 抓取海外消費回饋信用卡資訊"""
    url = "https://www.money101.com.tw/blog/credit-card-overseas-cashback"
    print(f"正在抓取: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # 嘗試解析文章中的表格或列表
        tables = soup.find_all("table")
        cards_data = []

        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:  # 跳過標題列
                cols = row.find_all(["td", "th"])
                if len(cols) >= 3:
                    card_info = {
                        "bank": cols[0].get_text(strip=True),
                        "name": cols[1].get_text(strip=True) if len(cols) > 1 else "",
                        "reward": cols[2].get_text(strip=True) if len(cols) > 2 else "",
                    }
                    cards_data.append(card_info)

        print(f"  從 Money101 取得 {len(cards_data)} 筆資料")
        return cards_data

    except requests.RequestException as e:
        print(f"  抓取失敗: {e}")
        return []


def fetch_card_compare_data():
    """從卡優新聞網抓取信用卡比較資料"""
    url = "https://www.cardu.com.tw/card/compare.php"
    print(f"正在抓取: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        cards_data = []
        # 解析卡片列表
        card_items = soup.find_all("div", class_=re.compile(r"card|item"))

        for item in card_items:
            title = item.find(["h2", "h3", "h4", "a"])
            if title:
                cards_data.append({
                    "name": title.get_text(strip=True),
                    "source": "cardu",
                })

        print(f"  從卡優新聞網取得 {len(cards_data)} 筆資料")
        return cards_data

    except requests.RequestException as e:
        print(f"  抓取失敗: {e}")
        return []


def parse_reward_rate(text):
    """從文字中解析回饋率數字"""
    matches = re.findall(r"(\d+\.?\d*)%", text)
    if matches:
        return max(float(m) for m in matches)
    return 0.0


def update_rewards_from_scraped(scraped_data, existing_rewards):
    """根據爬取的資料更新 rewards.json"""
    # 更新時間戳記
    existing_rewards["lastUpdated"] = datetime.now().strftime("%Y-%m-%d")

    # 嘗試匹配並更新現有卡片資料
    for scraped in scraped_data:
        bank = scraped.get("bank", "")
        name = scraped.get("name", "")
        reward_text = scraped.get("reward", "")

        if not reward_text:
            continue

        # 嘗試匹配現有卡片
        for reward in existing_rewards.get("rewards", []):
            card_id = reward["cardId"]
            # 簡單的模糊比對
            if bank and (bank in card_id or card_id in bank.lower()):
                rate = parse_reward_rate(reward_text)
                if rate > 0:
                    reward["overseas"]["defaultRate"] = rate
                    reward["overseas"]["note"] = reward_text
                    print(f"  更新 {card_id}: 海外回饋 {rate}%")

    return existing_rewards


def run_scraper():
    """執行爬蟲主程式"""
    print("=" * 60)
    print(f"台灣信用卡優惠爬蟲 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 讀取現有資料
    with open(REWARDS_FILE, "r", encoding="utf-8") as f:
        existing_rewards = json.load(f)

    # 爬取各來源
    all_scraped = []
    all_scraped.extend(fetch_money101_overseas_cards())
    all_scraped.extend(fetch_card_compare_data())

    if all_scraped:
        # 更新資料
        updated = update_rewards_from_scraped(all_scraped, existing_rewards)

        # 寫入檔案
        with open(REWARDS_FILE, "w", encoding="utf-8") as f:
            json.dump(updated, f, ensure_ascii=False, indent=2)

        print(f"\n已更新 {REWARDS_FILE}")
    else:
        print("\n未取得新資料，僅更新時間戳記")
        existing_rewards["lastUpdated"] = datetime.now().strftime("%Y-%m-%d")
        with open(REWARDS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_rewards, f, ensure_ascii=False, indent=2)

    print("爬蟲執行完成！")


if __name__ == "__main__":
    run_scraper()
