import cloudscraper
import re
from urllib.parse import urljoin

# URL utama untuk mengambil daftar siaran yang sedang berjalan
BASE_URL = "https://tructiepbongda24h.com/"

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

m3u_content = "#EXTM3U\n"

try:
    print("[*] Mengakses halaman utama untuk mencari laga live...")
    main_res = scraper.get(BASE_URL, timeout=20)
    
    if main_res.status_code == 200:
        # Cari semua link pertandingan langsung dari halaman depan
        match_links = re.findall(r'href=["\'](https?://tructiepbongda24h\.com/truc-tiep/[^"\']+)["\']', main_res.text)
        unique_matches = list(set(match_links))[:5] # Ambil maksimal 5 laga live
        
        print(f"[+] Ditemukan {len(unique_matches)} pertandingan live.")
        
        for index, match_url in enumerate(unique_matches, start=1):
            print(f"[*] Scraping Laga {index}: {match_url}")
            try:
                res = scraper.get(match_url, timeout=20)
                
                # Cari pola URL m3u8 niur.live dengan token txSecret
                m3u8_pattern = r'(https?://pull\.niur\.live/live/[^\s"\'<>]+\.m3u8\?[^\s"\'<>]+)'
                matches = re.findall(m3u8_pattern, res.text)
                
                if matches:
                    stream_url = matches[0]
                    print(f"    [+] Stream Ditemukan: {stream_url}")
                    
                    m3u_content += f'#EXTINF:-1 tvg-id="Match_{index}" group-title="NguyenBong Live", Live Match {index}\n'
                    m3u_content += '#EXTVLCOPT:http-referrer=https://tructiepbongda24h.com/\n'
                    m3u_content += '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n'
                    m3u_content += f'{stream_url}\n\n'
                else:
                    print("    [-] Stream URL tidak ditemukan / laga belum mulai.")
            except Exception as e:
                print(f"    [X] Error scraping match: {e}")
    else:
        print(f"[-] Gagal akses halaman utama. Status: {main_res.status_code}")

except Exception as e:
    print(f"[X] Error utama: {e}")

# Simpan hasil scraping ke file nguyenbong.m3u
with open("nguyenbong.m3u", "w", encoding="utf-8") as f:
    f.write(m3u_content)

print("[+] Pembaruan nguyenbong.m3u selesai!")
