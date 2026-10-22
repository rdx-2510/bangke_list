from playwright.sync_api import sync_playwright

BASE_URL = "https://tructiepbongda24h.com/"

def run():
    found_urls = []

    # Fungsi penyadap lalu lintas jaringan
    def handle_request(request):
        url = request.url
        if "pull.niur.live" in url and ".m3u8" in url:
            if url not in found_urls:
                found_urls.append(url)
                print(f"[+] Tembus! Ditemukan M3U8 Stream: {url}")

    with sync_playwright() as p:
        # Jalankan browser Chromium tanpa antarmuka grafis
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Pasang pendengar request jaringan
        page.on("request", handle_request)

        print("[*] Membuka halaman utama...")
        try:
            page.goto(BASE_URL, timeout=30000)
            page.wait_for_timeout(3000)

            # Ekstrak semua link pertandingan live
            links = page.locator('a[href*="/truc-tiep/"]').all()
            match_urls = []
            for link in links:
                href = link.get_attribute("href")
                if href and href not in match_urls:
                    match_urls.append(href)
            
            match_urls = match_urls[:5] # Ambil 5 pertandingan teratas
            print(f"[+] Ditemukan {len(match_urls)} laga live.")

            # Buka tiap halaman pertandingan dan tunggu player memuat stream
            for index, match_url in enumerate(match_urls, start=1):
                print(f"[*] Mengakses Laga {index}: {match_url}")
                try:
                    page.goto(match_url, timeout=30000)
                    # Beri jeda 8 detik agar JS player selesai memanggil m3u8
                    page.wait_for_timeout(8000) 
                except Exception as e:
                    print(f"    [X] Gagal memuat halaman: {e}")

        except Exception as e:
            print(f"[X] Error utama: {e}")

        browser.close()

    # Menyusun isi file nguyenbong.m3u
    m3u_content = "#EXTM3U\n"
    for idx, stream_url in enumerate(found_urls, start=1):
        m3u_content += f'#EXTINF:-1 tvg-id="Match_{idx}" group-title="NguyenBong Live", Live Match {idx}\n'
        m3u_content += '#EXTVLCOPT:http-referrer=https://tructiepbongda24h.com/\n'
        m3u_content += '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n'
        m3u_content += f'{stream_url}\n\n'

    with open("nguyenbong.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"[+] Pembaruan nguyenbong.m3u selesai! Total {len(found_urls)} stream didapat.")

if __name__ == "__main__":
    run()
