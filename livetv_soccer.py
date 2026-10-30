import requests
from bs4 import BeautifulSoup
import re

# Category 1 = Khusus Sepak Bola / Soccer
URL = "https://livetv.sx/enx/allupcoming/1/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def main():
    print("[*] Scraping LiveTV.sx (Khusus Sepak Bola)...")
    try:
        res = requests.get(URL, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        matches = soup.find_all('a', class_='live')
        m3u_content = "#EXTM3U\n"
        count = 0

        for m in matches[:15]:
            title = m.text.strip()
            if not title:
                continue
                
            link = m['href']
            if not link.startswith('http'):
                link = "https://livetv.sx" + link
                
            try:
                detail_res = requests.get(link, headers=HEADERS, timeout=10)
                html = detail_res.text
                
                # Filter webplayer & iframe non-iklan
                webplayers = re.findall(r'href=["\']([^"\']*webplayer[^"\']*)["\']', html)
                iframes = re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)
                
                valid_stream = None
                if webplayers:
                    wp = webplayers[0]
                    valid_stream = wp if wp.startswith('http') else "https://livetv.sx" + wp
                else:
                    for iframe_url in iframes:
                        if not iframe_url.startswith('http'):
                            iframe_url = "https:" + iframe_url if iframe_url.startswith('//') else "https://livetv.sx" + iframe_url
                        
                        if any(ad in iframe_url.lower() for ad in ['getbanner', 'ads.', 'banner', 'doubleclick', 'yandex']):
                            continue
                            
                        valid_stream = iframe_url
                        break

                if valid_stream:
                    count += 1
                    m3u_content += f'#EXTINF:-1 group-title="LiveTV Soccer", {title}\n'
                    m3u_content += f'{valid_stream}\n\n'
                    print(f"    [+] {title} -> {valid_stream}")

            except Exception:
                continue

        output_file = "livetv_soccer.m3u"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(m3u_content)

        print(f"\n[+] Selesai! {count} stream sepak bola tersimpan di {output_file}")

    except Exception as e:
        print(f"[X] Error: {e}")

if __name__ == "__main__":
    main()
