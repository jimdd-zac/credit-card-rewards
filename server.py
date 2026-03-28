#!/usr/bin/env python3
"""Simple HTTP server for the credit card rewards web app with search API."""

import http.server
import json
import os
import re
import urllib.parse
import posixpath

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_SCRAPER = True
except ImportError:
    HAS_SCRAPER = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


def search_money101(query):
    """Search Money101 for credit card info."""
    results = []
    url = f"https://www.money101.com.tw/search?q={urllib.parse.quote(query)}+信用卡"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for card-related links and info
        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)
            if "信用卡" in text and len(text) > 5:
                results.append({"title": text, "url": link["href"], "source": "Money101"})
            if len(results) >= 5:
                break
    except Exception as e:
        print(f"Money101 search error: {e}")
    return results


def search_card_info(query):
    """Search for credit card reward details from multiple sources."""
    cards_found = []

    # Try Money101 card page
    search_url = f"https://www.money101.com.tw/blog/{urllib.parse.quote(query)}"
    try:
        # Search Google-style from Money101
        url = f"https://www.money101.com.tw/creditcard"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find cards matching query
        for item in soup.find_all(["div", "a", "li"], string=re.compile(query, re.IGNORECASE)):
            text = item.get_text(strip=True)
            if len(text) > 3:
                cards_found.append(text)
    except Exception as e:
        print(f"Money101 card search error: {e}")

    # Try cardu.com.tw
    try:
        url = f"https://www.cardu.com.tw/search/?q={urllib.parse.quote(query)}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for item in soup.find_all(["a", "div", "td"]):
            text = item.get_text(strip=True)
            if query.lower() in text.lower() and len(text) > 5 and len(text) < 200:
                cards_found.append(text)
    except Exception as e:
        print(f"Cardu search error: {e}")

    return cards_found[:10]


def scrape_card_detail(query):
    """Try to scrape detailed card info from official bank websites first."""
    result = {
        "bank": "",
        "name": "",
        "network": "Visa",
        "overseasRate": 0,
        "domesticRate": 0,
        "foreignFee": 1.5,
        "feeNote": "免年費",
        "note": "",
        "countryRates": [],
        "rawTexts": [],
        "source": "",
    }

    # Parse bank name from query
    bank_keywords = {
        "中信": "中國信託", "中國信託": "中國信託",
        "玉山": "玉山銀行", "國泰": "國泰世華", "台新": "台新銀行",
        "富邦": "富邦銀行", "永豐": "永豐銀行", "聯邦": "聯邦銀行",
        "星展": "星展銀行", "匯豐": "匯豐銀行", "花旗": "花旗銀行",
        "渣打": "渣打銀行", "第一": "第一銀行", "華南": "華南銀行",
        "兆豐": "兆豐銀行", "合庫": "合庫銀行", "彰銀": "彰化銀行",
        "台北富邦": "富邦銀行", "元大": "元大銀行", "凱基": "凱基銀行",
        "新光": "新光銀行", "遠東": "遠東銀行", "樂天": "樂天銀行",
        "LINE Bank": "LINE Bank", "將來": "將來銀行",
    }

    for keyword, bank in bank_keywords.items():
        if keyword in query:
            result["bank"] = bank
            result["name"] = query.replace(keyword, "").replace("銀行", "").replace("信用卡", "").strip()
            break

    if not result["bank"]:
        result["name"] = query

    # === Step 1: Official bank website credit card listing pages ===
    bank_card_urls = {
        "中國信託": [
            "https://www.ctbcbank.com/content/dam/minisite/long/creditcard/cardlist/index.html",
            "https://www.ctbcbank.com/twrbo/zh_tw/index/card-credit/card-credit.html",
        ],
        "玉山銀行": [
            "https://www.esunbank.com/zh-tw/personal/credit-card/intro/all-cards",
        ],
        "國泰世華": [
            "https://www.cathaybk.com.tw/cathaybk/personal/product/credit-card/cards/",
        ],
        "台新銀行": [
            "https://www.taishinbank.com.tw/TSB/personal/credit-card/intro/overview/",
        ],
        "富邦銀行": [
            "https://www.fubon.com/banking/personal/credit_card/all_cards/all_cards.htm",
        ],
        "永豐銀行": [
            "https://bank.sinopac.com/sinopacBT/personal/credit-card/overview.html",
        ],
        "星展銀行": [
            "https://www.dbs.com.tw/personal-zh/cards/credit-cards.page",
        ],
        "匯豐銀行": [
            "https://www.hsbc.com.tw/credit-cards/",
        ],
        "樂天銀行": [
            "https://card.rakuten.com.tw/corp/credit/",
        ],
        "新光銀行": [
            "https://www.skbank.com.tw/credit_card",
        ],
        "元大銀行": [
            "https://www.yuantabank.com.tw/bank/credit-card/",
        ],
        "凱基銀行": [
            "https://www.kgibank.com/personal/card/credit",
        ],
        "聯邦銀行": [
            "https://card.ubot.com.tw/eCard/doCreditCard",
        ],
    }

    matched_bank = result["bank"]
    card_name_hint = result["name"] or query

    # Try official bank site first
    if matched_bank and matched_bank in bank_card_urls:
        for url in bank_card_urls[matched_bank]:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=15)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                page_text = soup.get_text()

                # Search for the card name
                search_terms = [card_name_hint, query]
                for term in search_terms:
                    if not term:
                        continue
                    idx = page_text.find(term)
                    if idx >= 0:
                        window = page_text[max(0, idx - 100):idx + 500]
                        result["rawTexts"].append(f"[{matched_bank}官網] " + window.strip().replace("\n", " ")[:200])
                        result["source"] = f"{matched_bank}官網"

                        _extract_rates(window, result)
                        break

                # Also look for card product links
                for a_tag in soup.find_all("a", href=True):
                    link_text = a_tag.get_text(strip=True)
                    if card_name_hint and card_name_hint in link_text:
                        detail_url = a_tag["href"]
                        if not detail_url.startswith("http"):
                            from urllib.parse import urljoin
                            detail_url = urljoin(url, detail_url)

                        try:
                            d_resp = requests.get(detail_url, headers=HEADERS, timeout=10)
                            if d_resp.status_code == 200:
                                d_soup = BeautifulSoup(d_resp.text, "html.parser")
                                d_text = d_soup.get_text()
                                result["source"] = f"{matched_bank}官網（卡片頁面）"
                                _extract_rates(d_text, result)
                                _extract_card_meta(d_text, result)

                                # Get relevant snippets
                                for line in d_text.split("\n"):
                                    line = line.strip()
                                    if ("回饋" in line or "海外" in line or "國內" in line) and "%" in line and 8 < len(line) < 200:
                                        result["rawTexts"].append(f"[官網] {line}")
                        except Exception:
                            pass
                        break

            except Exception as e:
                print(f"Official bank scrape error ({matched_bank}): {e}")

    # === Step 2: DuckDuckGo search - try official site first, then general ===
    import time
    ddg_queries = []
    if matched_bank:
        domain = _get_bank_domain(matched_bank)
        if domain:
            ddg_queries.append(f"site:{domain} {card_name_hint} 回饋")
    ddg_queries.append(f"{query} 信用卡 回饋 海外 國內 %")

    for ddg_q in ddg_queries:
        if result["overseasRate"] > 0 and result["domesticRate"] > 0:
            break
        try:
            time.sleep(0.5)  # Avoid rate limiting
            search_q = urllib.parse.quote(ddg_q)
            url = f"https://html.duckduckgo.com/html/?q={search_q}"
            resp = requests.get(url, headers={
                **HEADERS,
                "Referer": "https://duckduckgo.com/",
            }, timeout=15)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract from result snippets
            for snippet_el in soup.find_all("a", class_="result__snippet"):
                text = snippet_el.get_text(strip=True)
                if "%" in text and len(text) > 10:
                    _extract_rates(text, result)
                    _extract_card_meta(text, result)
                    if ("回饋" in text or "海外" in text or "國內" in text) and len(text) < 250:
                        result["rawTexts"].append(text)

            # Also check result titles
            for title_el in soup.find_all("a", class_="result__a"):
                text = title_el.get_text(strip=True)
                if "%" in text and len(text) > 5:
                    _extract_rates(text, result)
                    if "回饋" in text:
                        result["rawTexts"].append(text)

            # Follow first official bank link for detailed info
            bank_domains = [
                "ctbcbank.com", "esunbank.com", "cathaybk.com", "taishinbank.com",
                "fubon.com", "sinopac.com", "dbs.com", "hsbc.com",
                "rakuten", "skbank.com", "yuantabank.com", "kgibank.com", "ubot.com",
            ]
            for a_tag in soup.find_all("a", class_="result__url"):
                href = a_tag.get("href", "")
                if any(d in href for d in bank_domains):
                    try:
                        d_resp = requests.get(href, headers=HEADERS, timeout=10)
                        if d_resp.status_code == 200:
                            d_text = BeautifulSoup(d_resp.text, "html.parser").get_text()
                            result["source"] = "官網"
                            _extract_rates(d_text, result)
                            _extract_card_meta(d_text, result)
                            for line in d_text.split("\n"):
                                line = line.strip()
                                if ("回饋" in line or "海外" in line) and "%" in line and 8 < len(line) < 200:
                                    result["rawTexts"].append(f"[官網] {line}")
                            if result["overseasRate"] > 0 or result["domesticRate"] > 0:
                                break
                    except Exception:
                        pass
                    break

        except Exception as e:
            print(f"DuckDuckGo search error: {e}")

    # === Step 3: Bing search as additional fallback ===
    if result["overseasRate"] == 0 and result["domesticRate"] == 0:
        try:
            search_q = urllib.parse.quote(f"{query} 信用卡 回饋")
            url = f"https://www.bing.com/search?q={search_q}&setlang=zh-TW"
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for el in soup.find_all(["p", "li", "span", "div"]):
                    text = el.get_text(strip=True)
                    if "%" in text and ("回饋" in text or "海外" in text or "現金" in text) and 10 < len(text) < 250:
                        _extract_rates(text, result)
                        _extract_card_meta(text, result)
                        result["rawTexts"].append(text)
                        if not result["source"]:
                            result["source"] = "網路搜尋"
        except Exception as e:
            print(f"Bing search error: {e}")

    # === Step 4: Direct official card page if we know the bank ===
    if result["overseasRate"] == 0 and result["domesticRate"] == 0 and matched_bank:
        # Try the bank's card listing API/page that might be static
        direct_urls = {
            "樂天銀行": "https://card.rakuten.com.tw/corp/credit/",
            "玉山銀行": "https://www.esunbank.com/zh-tw/personal/credit-card/intro/all-cards",
            "國泰世華": "https://www.cathaybk.com.tw/cathaybk/personal/product/credit-card/",
            "台新銀行": "https://www.taishinbank.com.tw/TSB/personal/credit-card/intro/overview/",
        }
        if matched_bank in direct_urls:
            try:
                resp = requests.get(direct_urls[matched_bank], headers=HEADERS, timeout=15)
                if resp.status_code == 200:
                    text = BeautifulSoup(resp.text, "html.parser").get_text()
                    _extract_rates(text, result)
                    _extract_card_meta(text, result)
                    for line in text.split("\n"):
                        line = line.strip()
                        if card_name_hint and card_name_hint in line and "%" in line and 8 < len(line) < 200:
                            result["rawTexts"].append(f"[{matched_bank}官網] {line}")
                    if result["overseasRate"] > 0 or result["domesticRate"] > 0:
                        result["source"] = f"{matched_bank}官網"
            except Exception as e:
                print(f"Direct bank page error: {e}")

    # Deduplicate rawTexts
    seen = set()
    unique_texts = []
    for t in result["rawTexts"]:
        short = t[:60]
        if short not in seen:
            seen.add(short)
            unique_texts.append(t)
    result["rawTexts"] = unique_texts[:10]

    if result["source"]:
        result["rawTexts"].insert(0, f"資料來源：{result['source']}")

    return result


def _get_bank_domain(bank_name):
    """Get the official domain for a bank."""
    domains = {
        "中國信託": "ctbcbank.com",
        "玉山銀行": "esunbank.com",
        "國泰世華": "cathaybk.com.tw",
        "台新銀行": "taishinbank.com.tw",
        "富邦銀行": "fubon.com",
        "永豐銀行": "sinopac.com",
        "聯邦銀行": "ubot.com.tw",
        "星展銀行": "dbs.com.tw",
        "匯豐銀行": "hsbc.com.tw",
        "樂天銀行": "rakuten-bank.com.tw",
        "新光銀行": "skbank.com.tw",
        "元大銀行": "yuantabank.com.tw",
        "凱基銀行": "kgibank.com",
    }
    return domains.get(bank_name, "")


def _extract_rates(text, result):
    """Extract overseas/domestic rates from text."""
    # Overseas rate patterns
    for pattern in [
        r'海外[消費刷卡回饋]*[^%\d]{0,15}?(\d+\.?\d*)%',
        r'國外[消費刷卡回饋]*[^%\d]{0,15}?(\d+\.?\d*)%',
        r'境外[消費刷卡回饋]*[^%\d]{0,15}?(\d+\.?\d*)%',
        r'國外實體[^%\d]{0,10}?(\d+\.?\d*)%',
    ]:
        m = re.search(pattern, text)
        if m:
            rate = float(m.group(1))
            if 0.5 <= rate <= 20 and rate > result["overseasRate"]:
                result["overseasRate"] = rate

    # "國內外" pattern - applies to both
    m = re.search(r'國內外[一般消費刷卡回饋最高享]*[^%\d]{0,15}?(\d+\.?\d*)%', text)
    if m:
        rate = float(m.group(1))
        if 0.1 <= rate <= 20:
            if rate > result["domesticRate"]:
                result["domesticRate"] = rate
            if rate > result["overseasRate"]:
                result["overseasRate"] = rate

    # Domestic rate patterns
    for pattern in [
        r'國內[一般消費刷卡回饋最高享]*[^%\d]{0,15}?(\d+\.?\d*)%',
        r'一般[消費刷卡回饋最高享]*[^%\d]{0,15}?(\d+\.?\d*)%',
    ]:
        m = re.search(pattern, text)
        if m:
            rate = float(m.group(1))
            if 0.1 <= rate <= 20 and rate > result["domesticRate"]:
                result["domesticRate"] = rate

    # Specific channel patterns (網購/行動支付 etc.)
    for pattern in [
        r'網[路購][消費購物]*[最高享]*[^%\d]{0,10}?(\d+\.?\d*)%',
        r'行動支付[最高享]*[^%\d]{0,10}?(\d+\.?\d*)%',
        r'數位[通路訂閱消費]*[最高享]*[^%\d]{0,10}?(\d+\.?\d*)%',
    ]:
        m = re.search(pattern, text)
        if m:
            rate = float(m.group(1))
            if 1 <= rate <= 20:
                if not result.get("note") or len(result["note"]) < 5:
                    label = "網購" if "網" in pattern else "行動支付" if "行動" in pattern else "數位通路"
                    result["note"] = f"{label}最高 {rate}%"

    # Foreign tx fee
    fee_m = re.search(r'手續費[^%\d]{0,10}?(\d+\.?\d*)%', text)
    if fee_m:
        fee = float(fee_m.group(1))
        if 0 < fee <= 3:
            result["foreignFee"] = fee


def _extract_card_meta(text, result):
    """Extract card network and other metadata."""
    if "JCB" in text:
        result["network"] = "JCB"
    elif "Mastercard" in text or "萬事達" in text:
        result["network"] = "Mastercard"
    elif "AMEX" in text or "美國運通" in text:
        result["network"] = "AMEX"

    if "免年費" in text or "免繳年費" in text:
        result["feeNote"] = "免年費"
    elif re.search(r'年費[^，。\n]{0,5}(\d[\d,]+)', text):
        m = re.search(r'年費[^，。\n]{0,5}(\d[\d,]+)', text)
        result["feeNote"] = f"年費 ${m.group(1)}"


def search_merchant_cards(merchant):
    """Search the web for best credit cards for a specific merchant/store."""
    recommendations = []

    # Try multiple search sources
    search_urls = [
        # DuckDuckGo HTML (more lenient than Google)
        f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(f'{merchant} 信用卡 推薦 回饋')}",
        # Money101 blog articles
        f"https://www.money101.com.tw/blog/best-cashback-credit-cards",
        f"https://www.money101.com.tw/blog/credit-card-overseas-cashback",
    ]

    for url in search_urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")

            # For DuckDuckGo: extract snippets
            if "duckduckgo" in url:
                for result in soup.find_all("a", class_="result__snippet"):
                    text = result.get_text(strip=True)
                    if "%" in text and len(text) > 15:
                        rate_matches = re.findall(r'(\d+\.?\d*)%', text)
                        for rm in rate_matches:
                            rate = float(rm)
                            if 0.5 < rate <= 20:
                                recommendations.append({"text": text[:200], "rate": rate})
                                break

                # Also check result titles and snippets more broadly
                for result in soup.find_all(["a", "td", "span"]):
                    text = result.get_text(strip=True)
                    if "%" in text and ("回饋" in text or "現金" in text or "刷卡" in text) and 15 < len(text) < 250:
                        rate_matches = re.findall(r'(\d+\.?\d*)%', text)
                        for rm in rate_matches:
                            rate = float(rm)
                            if 0.5 < rate <= 20:
                                recommendations.append({"text": text[:200], "rate": rate})
                                break

            else:
                # For Money101 pages: search for merchant-related content
                page_text = soup.get_text()
                lines = page_text.split("\n")
                for line in lines:
                    line = line.strip()
                    if not line or len(line) < 10 or len(line) > 250:
                        continue
                    # Check if line mentions the merchant or related keywords
                    if "%" in line and ("回饋" in line or "現金" in line):
                        rate_matches = re.findall(r'(\d+\.?\d*)%', line)
                        for rm in rate_matches:
                            rate = float(rm)
                            if 0.5 < rate <= 20:
                                recommendations.append({"text": line[:200], "rate": rate})
                                break

        except Exception as e:
            print(f"Merchant search error ({url[:50]}): {e}")

    # Try Google as last resort
    try:
        search_q = urllib.parse.quote(f"{merchant} 信用卡 推薦 回饋 最高")
        url = f"https://www.google.com.tw/search?q={search_q}&hl=zh-TW"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for div in soup.find_all(["div", "span"]):
                text = div.get_text(strip=True)
                if 15 < len(text) < 250 and "%" in text and ("回饋" in text or "現金" in text or "推薦" in text):
                    rate_match = re.search(r'(\d+\.?\d*)%', text)
                    if rate_match:
                        rate = float(rate_match.group(1))
                        if 0.5 < rate <= 20:
                            recommendations.append({"text": text[:200], "rate": rate})
    except Exception as e:
        print(f"Merchant Google search error: {e}")

    # Deduplicate
    seen = set()
    unique = []
    for r in recommendations:
        key = r["text"][:50]
        if key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda x: x["rate"], reverse=True)

    return unique[:10]


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/api/search":
            self.handle_search(parsed)
            return
        elif parsed.path == "/api/merchant":
            self.handle_merchant(parsed)
            return
        elif parsed.path == "/" or parsed.path == "/index.html":
            self.path = "/web/index.html"
        return super().do_GET()

    def handle_search(self, parsed):
        params = urllib.parse.parse_qs(parsed.query)
        query = params.get("q", [""])[0].strip()

        if not query:
            self.send_json({"error": "請輸入搜尋關鍵字"})
            return

        if not HAS_SCRAPER:
            self.send_json({"error": "伺服器缺少 requests/beautifulsoup4 套件"})
            return

        result = scrape_card_detail(query)
        self.send_json(result)

    def handle_merchant(self, parsed):
        params = urllib.parse.parse_qs(parsed.query)
        merchant = params.get("q", [""])[0].strip()

        if not merchant:
            self.send_json({"error": "請輸入商家名稱"})
            return

        if not HAS_SCRAPER:
            self.send_json({"recommendations": [], "error": "伺服器缺少 requests/beautifulsoup4 套件"})
            return

        recs = search_merchant_cards(merchant)
        self.send_json({"merchant": merchant, "recommendations": recs})

    def send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def translate_path(self, path):
        path = path.split("?", 1)[0].split("#", 1)[0]
        path = urllib.parse.unquote(path)
        path = posixpath.normpath(path)
        parts = path.split("/")
        result = BASE_DIR
        for part in parts:
            if part and part != "..":
                result = os.path.join(result, part)
        return result

    def end_headers(self):
        if "Cache-Control" not in {h[0] for h in self._headers_buffer if isinstance(h, tuple)}:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    os.chdir(BASE_DIR)
    with http.server.HTTPServer(("", PORT), Handler) as httpd:
        print(f"Server running at http://localhost:{PORT}")
        if not HAS_SCRAPER:
            print("WARNING: requests/beautifulsoup4 not installed. Search API disabled.")
            print("  pip3 install requests beautifulsoup4")
        httpd.serve_forever()
