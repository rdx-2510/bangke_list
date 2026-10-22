import cloudscraper
import re

# Daftar URL pertandingan yang mau di-scrape
match_urls = [
    "https://tructiepbongda24h.com/truc-tiep/juventus-vs-stade-rennais-fc-22-10-2026/",
    "https://tructiepbongda24h.com/truc-tiep/al-fateh-vs-al-shabab-22-10-2026/"
]

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

m3u_content = "#EXTM3U\n"

for index, url in enumerate(match_urls, start=1):
    try:
        print(f"[*] Scraping: {url}")
        res = scraper.get(url, timeout=20)
        
        if res.status_code == 200:
            # Pola regex untuk menangkap URL niur.live beserta token txSecret & txTime
            m3u8_pattern = r'(https?://pull\.niur\.live/live/[^\s"\'<>]+\.m3u8\?[^\s"\'<>]+)'
            matches = re.findall(m3u8_pattern, res.text)
            
            if matches:
                stream_url = matches[0]
                print(f"   [+] Ditemukan Stream URL: {stream_url}")
                
                # Menambahkan header khusus agar bisa di-stream tanpa error HTTP 403
                m3u_content += f'#EXTINF:-1 tvg-id="Match_{index}" group-title="NguyenBong Live", Live Stream Match {index}\n'
                m3u_content += '#EXTVLCOPT:http-referrer=https://tructiepbongda24h.com/\n'
                m3u_content += '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n'
                m3u_content += f'{stream_url}\n\n'
            else:
                print("   [-] Stream URL tidak ditemukan.")
    except Exception as e:
        print(f"   [X] Error: {e}")

# Simpan hasil scraping ke file nguyenbong.m3u
with open("nguyenbong.m3u", "w", encoding="utf-8") as f:
    f.write(m3u_content)

print("[+] File nguyenbong.m3u berhasil diperbarui!")
