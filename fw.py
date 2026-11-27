import json
import re
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "http://www.fawanews.sc/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

NON_FOOTBALL_KEYWORDS = [
    # Basket & turnamen FIBA / internasional
    "nba", "wnba", "fiba", "basketball", "basket",
    "u17 world championship", "u19 world championship",
    "euroleague", "eurocup", "eurobasket", "americup", "afrobasket",
    "ncaa", "acb", "bbl", "lnb", "lega basket", "vtb",
    "pba", "kbl", "b.league", "bleague", "ibl", "nbl", "cba",
    # Cabang olahraga lain yang sering muncul di FawaNews
    "nhl", "hockey", "ice hockey", "nfl", "mlb", "baseball",
    "tennis", "atp", "wta", "ufc", "mma", "boxing",
    "formula 1", "f1", "motogp", "rugby", "cricket",
    "volleyball", "handball", "snooker", "darts", "golf", "afl"
]


def is_non_football(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(kw)}\b", lowered) if len(kw) <= 3 else kw in lowered for kw in NON_FOOTBALL_KEYWORDS)


def is_other_sport_on_sofascore(title: str) -> bool:
    """
    Cek khusus laga timnas/kelompok umur (misal 'Indonesia vs Thailand' atau 'Honduras U17 vs Japan U17')
    yang di FawaNews tidak mencantumkan nama cabang olahraga.
    Mengembalikan True HANYA jika SofaScore memastikan cabang olahraganya BUKAN football.
    """
    if " vs " not in title.lower():
        return False

    # Jalankan cek ini hanya untuk laga non-klub (tanpa FC/CF/United/dll) atau laga U17-U23
    is_club = re.search(r"\b(fc|cf|sc|ac|united|city|rovers|athletic|real|inter|sporting|dynamo|lokomotiv|persepolis)\b", title, re.IGNORECASE)
    if is_club:
        return False

    try:
        search_url = f"https://api.sofascore.com/api/v1/search/events?q={requests.utils.quote(title)}&page=0"
        res = requests.get(
            search_url,
            headers={
                "User-Agent": HEADERS["User-Agent"],
                "Accept": "application/json",
                "Referer": "https://www.sofascore.com/",
            },
            timeout=4,
        )
        if res.status_code == 200:
            events = res.json().get("events", [])
            if events:
                top_sport = (
                    events[0]
                    .get("tournament", {})
                    .get("category", {})
                    .get("sport", {})
                    .get("slug", "")
                    .lower()
                )
                if top_sport and top_sport != "football":
                    return True
    except Exception:
        pass

    return False


def get_all_matches():
    try:
        res = requests.get(BASE_URL, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return []
        soup = BeautifulSoup(res.text, "html.parser")
        matches = []
        seen_urls = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.endswith(".html") and href not in [
                "index.html",
                "contact.html",
                "privacy.html",
            ]:
                safe_href = href.replace(" ", "%20")
                full_url = (
                    safe_href
                    if safe_href.startswith("http")
                    else BASE_URL + safe_href
                )
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                # Gabungkan teks link, atribut alt/src ikon olahraga di dekat link, dan judul file
                link_text = a_tag.get_text(" ", strip=True)
                img_hints = " ".join(
                    f"{img.get('alt', '')} {img.get('src', '')}"
                    for img in a_tag.find_all("img")
                )
                parent_text = a_tag.parent.get_text(" ", strip=True) if a_tag.parent else ""
                context_str = f"{href} {link_text} {img_hints} {parent_text}"

                if is_non_football(context_str):
                    clean_name = full_url.split("/")[-1].replace(".html", "").replace("%20", " ")
                    print(f"[FILTER] Dilewati (Non-Football di Beranda): {clean_name}")
                    continue

                matches.append(full_url)
        return matches
    except Exception:
        return []


def extract_stream(match_url):
    page_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Referer": match_url,
        "Origin": "http://www.fawanews.sc",
    }
    try:
        res = requests.get(match_url, headers=page_headers, timeout=10)
        html = res.text

        # Lapis 2: Cek judul halaman detail jika beranda belum mencantumkan nama cabang olahraga
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if title_match and is_non_football(title_match.group(1)):
            return "SKIP_NON_FOOTBALL"

        d1 = re.search(r'var d1 = "(.*?)";', html)
        d2 = re.search(r'var d2 = "(.*?)";', html)
        d3 = re.search(r'var d3 = "(.*?)";', html)
        if d1 and d2 and d3:
            return d1.group(1) + d2.group(1) + d3.group(1)
    except Exception:
        pass
    return None


def main():
    match_links = get_all_matches()
    print(f"[+] Ditemukan {len(match_links)} kandidat jadwal sepak bola.\n")

    if not match_links:
        print(
            "[!] Daftar jadwal kosong / gagal dimuat, file lama dipertahankan."
        )
        return

    m3u_content = "#EXTM3U\n"
    json_matches = []
    success_count = 0

    for idx, url in enumerate(match_links, 1):
        raw_title = (
            url.split("/")[-1].replace(".html", "").replace("%20", " ")
        )
        print(f"[{idx}/{len(match_links)}] Memproses: {raw_title}")

        # Lapis 1 & 3: Cek kata kunci judul + verifikasi cabang olahraga laga timnas/U17 di SofaScore
        if is_non_football(raw_title) or is_other_sport_on_sofascore(raw_title):
            print("    └─ [FILTER] Dilewati (Bukan Sepak Bola)")
            continue

        team_a = raw_title
        team_b = ""
        if " vs " in raw_title.lower():
            parts = re.split(r"\s+vs\s+", raw_title, flags=re.IGNORECASE)
            if len(parts) >= 2:
                team_a = parts[0].strip()
                team_b = parts[1].strip()

        raw_m3u8 = extract_stream(url)
        if raw_m3u8 == "SKIP_NON_FOOTBALL":
            print("    └─ [FILTER] Dilewati (Judul Halaman Non-Football)")
            continue

        if raw_m3u8:
            print(f"    └─ [OK] {raw_m3u8}")

            m3u_content += f"#EXTINF:-1, FawaNews - {raw_title}\n"
            m3u_content += (
                f"#EXTVLCOPT:http-user-agent={HEADERS['User-Agent']}\n"
            )
            m3u_content += f"#EXTVLCOPT:http-referrer={url}\n"
            m3u_content += f"{raw_m3u8}\n"

            json_matches.append(
                {
                    "status": "LIVE",
                    "Category": "Football",
                    "event_name": raw_title,
                    "timestamp": int(time.time()),
                    "eventInfo": {
                        "teamA": team_a,
                        "teamB": team_b,
                        "teamAFlag": "",
                        "teamBFlag": "",
                        "eventName": "FawaNews Live",
                        "event_logo": "",
                        "startTime": time.strftime("%d/%m/%Y %I:%M:%S %p"),
                    },
                    "streams": [
                        {
                            "channel_name": "FawaNews",
                            "stream_url": raw_m3u8,
                            "referer": url,
                            "user_agent": HEADERS["User-Agent"],
                        }
                    ],
                }
            )

            success_count += 1
        else:
            print("    └─ [SKIP]")

    if success_count == 0:
        print("\n[!] 0 siaran ditemukan, file lama dipertahankan.")
        return

    with open("bangke_list.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    json_output = {
        "name": "Sports Data",
        "last_update_time": time.strftime("%I:%M:%S %p %d-%m-%Y"),
        "total_matches": len(json_matches),
        "live_match": success_count,
        "matches": json_matches,
    }

    with open("fawanews.json", "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=4)

    print(f"\n[+] Selesai! Berhasil mengekstrak {success_count} siaran sepak bola.")


if __name__ == "__main__":
    main()
