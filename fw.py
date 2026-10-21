import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "http://www.fawanews.sc/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_all_matches():
    try:
        res = requests.get(BASE_URL, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return []
        soup = BeautifulSoup(res.text, 'html.parser')
        matches = []
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if href.endswith('.html') and href not in ['index.html', 'contact.html', 'privacy.html']:
                safe_href = href.replace(' ', '%20')
                full_url = safe_href if safe_href.startswith('http') else BASE_URL + safe_href
                if full_url not in matches:
                    matches.append(full_url)
        return matches
    except Exception:
        return []

def extract_stream(match_url):
    page_headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Referer": match_url,
        "Origin": "http://www.fawanews.sc"
    }
    try:
        res = requests.get(match_url, headers=page_headers, timeout=10)
        html = res.text
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
    print(f"[+] Ditemukan {len(match_links)} jadwal siaran.\n")
    
    m3u_content = "#EXTM3U\n"
    success_count = 0
    
    for idx, url in enumerate(match_links, 1):
        match_title = url.split('/')[-1].replace('.html', '').replace('%20', ' ')
        print(f"[{idx}/{len(match_links)}] Memproses: {match_title}")
        
        raw_m3u8 = extract_stream(url)
        if raw_m3u8:
            print(f"    └─ [OK] {raw_m3u8}")
            m3u_content += f"#EXTINF:-1, FawaNews - {match_title}\n"
            m3u_content += f"#EXTVLCOPT:http-user-agent={HEADERS['User-Agent']}\n"
            m3u_content += f"#EXTVLCOPT:http-referrer={url}\n"
            m3u_content += f"{raw_m3u8}\n"
            success_count += 1
        else:
            print("    └─ [SKIP]")
            
    # Nama file disesuaikan menjadi bangke_list.m3u
    with open("bangke_list.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)
        
    print(f"\n[+] Selesai! Berhasil mengekstrak {success_count} siaran.")

if __name__ == "__main__":
    main()
