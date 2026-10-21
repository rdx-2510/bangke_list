import re
import random
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://roxiestreams.info"
SOCCER_URL = "https://roxiestreams.info/soccer"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_active_domains():
    """Sedot daftar domain aktif dari domainsz77.txt, fallback jika gagal"""
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
    """Sedot semua link pertandingan soccer dari halaman /soccer"""
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
    """Ekstrak parameter getRandomStream dan rakit URL m3u8"""
    try:
        res = requests.get(match_url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return None
        html = res.text
        
        # Ekstrak parameter dari getRandomStream('file.m3u8', 'subdomain')
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
    success_count = 0
    
    for idx, (url, title) in enumerate(matches, 1):
        print(f"[{idx}/{len(matches)}] Memproses: {title}")
        stream_url = extract_stream(url, domains)
        if stream_url:
            print(f"    └─ [OK] {stream_url}")
            m3u_content += f"#EXTINF:-1, RoxieSoccer - {title}\n"
            m3u_content += f"#EXTVLCOPT:http-user-agent={HEADERS['User-Agent']}\n"
            m3u_content += f"#EXTVLCOPT:http-referrer={BASE_URL}/\n"
            m3u_content += f"{stream_url}\n"
            success_count += 1
        else:
            print("    └─ [SKIP]")
            
    output_file = "roxi_soccer.m3u"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(m3u_content)
        
    print(f"\n[+] Selesai! Berhasil mengekstrak {success_count} siaran.")

if __name__ == "__main__":
    main()
