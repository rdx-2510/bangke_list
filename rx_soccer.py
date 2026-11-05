import json
import random
import re
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://roxiestreams.info"
SOCCER_URL = "https://roxiestreams.info/soccer"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_active_domains():
    try:
        res = requests.get(f"{BASE_URL}/domainsz77.txt", headers=HEADERS, timeout=5)
        if res.status_code == 200 and res.text.strip():
            domains = [d.strip() for d in res.text.strip().split('\n') if d.strip()]
            if domains:
                return domains
    except Exception:
        pass
    return ["shadow-ran.online"]

def get_soccer_matches():
    try:
        res = requests.get(SOCCER_URL, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return []
        soup = BeautifulSoup(res.text, 'html.parser')
        matches = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'soccer-streams-' in href:
                full_url = href if href.startswith('http') else f"{BASE_URL}/{href.lstrip('/')}"
                title = a.text.strip() or full_url.split('/')[-1]
                if (full_url, title) not in matches:
                    matches.append((full_url, title))
        return matches
    except Exception:
        return []

def extract_stream(match_url, domains):
    try:
        res = requests.get(match_url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return None
        html = res.text
        match = re.search(r"getRandomStream\(\s*['\"](.*?)['\"]\s*(?:,\s*['\"](.*?)['\"])?\)", html)
        if match:
            stream_path = match.group(1)
            subdomain = match.group(2) if match.group(2) else "admin2"
            selected_domain = random.choice(domains)
            return f"https://{subdomain}.{selected_domain}/{stream_path}"
    except Exception:
        pass
    return None

def main():
    print("[*] Mengambil daftar domain aktif...")
    domains = get_active_domains()
    print(f"[+] Domain aktif: {domains}")

    print("\n[*] Mengambil daftar laga RoxieStreams Soccer...")
    matches = get_soccer_matches()
    print(f"[+] Ditemukan {len(matches)} jadwal laga.\n")

    m3u_content = "#EXTM3U\n"
    json_matches = []
    success_count = 0

    for idx, (url, title) in enumerate(matches, 1):
        print(f"[{idx}/{len(matches)}] Memproses: {title}")

        team_a = title
        team_b = ""
        if " vs " in title.lower():
            parts = re.split(r'\s+vs\s+', title, flags=re.IGNORECASE)
            if len(parts) >= 2:
                team_a = parts[0].strip()
                team_b = parts[1].strip()

        stream_url = extract_stream(url, domains)
        if stream_url:
            print(f"    └─ [OK] {stream_url}")
            
            m3u_content += f"#EXTINF:-1, RoxieSoccer - {title}\n"
            m3u_content += f"#EXTVLCOPT:http-user-agent={HEADERS['User-Agent']}\n"
            m3u_content += f"#EXTVLCOPT:http-referrer={BASE_URL}/\n"
            m3u_content += f"{stream_url}\n"

            json_matches.append({
                "status": "LIVE",
                "Category": "Football",
                "event_name": title,
                "timestamp": int(time.time()),
                "eventInfo": {
                    "teamA": team_a,
                    "teamB": team_b,
                    "teamAFlag": "",
                    "teamBFlag": "",
                    "eventName": "RoxieStreams Live",
                    "event_logo": "",
                    "startTime": time.strftime("%d/%m/%Y %I:%M:%S %p")
                },
                "streams": [
                    {
                        "channel_name": "RoxieSoccer",
                        "stream_url": stream_url,
                        "referer": f"{BASE_URL}/",
                        "user_agent": HEADERS['User-Agent']
                    }
                ]
            })

            success_count += 1
        else:
            print("    └─ [SKIP]")

    output_m3u = "roxi_soccer.m3u"
    with open(output_m3u, "w", encoding="utf-8") as f:
        f.write(m3u_content)

    json_output = {
        "name": "RoxieStreams Sports Data",
        "owner": "Piyan BangkeTV",
        "telegram_channel": "https://t.me/bangketv",
        "last_update_time": time.strftime("%I:%M:%S %p %d-%m-%Y"),
        "total_matches": len(matches),
        "live_match": success_count,
        "matches": json_matches
    }
    
    output_json = "roxi_soccer.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(json_output, f, ensure_ascii=False, indent=4)

    print(f"\n[+] Selesai! Berhasil mengekstrak {success_count} siaran.")

if __name__ == "__main__":
    main()
