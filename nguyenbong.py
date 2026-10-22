from playwright.sync_api import sync_playwright

# Penanganan impor stealth agar tidak error di berbagai versi paket
try:
    from playwright_stealth.stealth import stealth_sync
except ImportError:
    try:
        from playwright_stealth import stealth_sync
    except ImportError:
        stealth_sync = None

BASE_URL = "https://tructiepbongda24h.com/"

def run():
    found_urls = []

    def handle_response(response):
        url = response.url
        if "pull.niur.live" in url and ".m3u8" in url:
            if url not in found_urls:
                found_urls.append(url)
                print(f"[+] TEMBUS! Stream URL: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale="en-US"
        )
        page = context.new_page()
        
        # Sembunyikan tanda otomatisasi navigator
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Jalankan stealth jika modul berhasil dimuat
        if stealth_sync:
            try:
                stealth_sync(page)
            except Exception:
                pass

        page.on("response", handle_response)

        print("[*] Membuka halaman utama...")
        try:
            page.goto(BASE_URL, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            match_links = page.locator('a[href*="/truc-tiep/"]').all()
            match_urls = []
            for link in match_links:
                href = link.get_attribute("href")
                if href and href not in match_urls:
                    match_urls.append(href)
            
            match_urls = match_urls[:3]
            print(f"[+] Ditemukan {len(match_urls)} laga live.")

            for index, match_url in enumerate(match_urls, start=1):
                print(f"\n[*] Mengakses Laga {index}: {match_url}")
                try:
                    page.goto(match_url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(5000)
                    print(f"    -> Judul Laga: {page.title()}")

                    if "Just a moment" not in page.title():
                        page.mouse.click(640, 360)
                        page.wait_for_timeout(5000)
                except Exception as e:
                    print(f"    [X] Gagal memuat laga: {e}")

        except Exception as e:
            print(f"[X] Error utama: {e}")

        browser.close()

    m3u_content = "#EXTM3U\n"
    for idx, stream_url in enumerate(found_urls, start=1):
        m3u_content += f'#EXTINF:-1 tvg-id="Match_{idx}" group-title="NguyenBong Live", Live Match {idx}\n'
        m3u_content += '#EXTVLCOPT:http-referrer=https://tructiepbongda24h.com/\n'
        m3u_content += '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)\n'
        m3u_content += f'{stream_url}\n\n'

    with open("nguyenbong.m3u", "w", encoding="utf-8") as f:
        f.write(m3u_content)

    print(f"\n[+] Selesai! Total {len(found_urls)} stream didapat.")

if __name__ == "__main__":
    run()
