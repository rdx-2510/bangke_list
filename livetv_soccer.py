import requests
from bs4 import BeautifulSoup
import re

URL = "https://livetv.sx/enx/allupcoming/1/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Daftar kata kunci yang dipastikan bukan sepak bola
NON_SOCCER_KEYWORDS = [
    'grand_prix', 'formula', 'atp', 'wta', 'nhl', 'nba', 
    'euroleague', 'khl', 'vtb', 'handball', 'volleyball', 
    'table_tennis', 'billiards', 'darts', 'rugby'
]

def main():
    print("[*] Scraping LiveTV.sx (Murni Sepak Bola)...")
    try:
        res = requests.get(URL, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        matches = soup.find_all('a', class_='live')
        m3u_content = "#EXTM3U\n"
        count = 0

        for m in matches:
            if count >= 15:
                break
                
            title = m.text.strip()
            if not title:
                continue
            
            link = m['href']
            if not link.startswith('http'):
                link = "https://livetv.sx" + link
                
            # Filter berdasarkan URL link (mengabaikan balapan, basket, tenis, dll)
            is_valid_soccer = True
            for kw in NON_SOCCER_KEYWORDS:
                if kw in link.lower() or kw in title.lower():
                    is_valid_soccer = False
                    break
            
            # Jika terdeteksi Simulcast, lewati juga
            if "simulcast" in title.lower():
                is_valid_soccer = False

            if not is_valid_soccer:
                continue
                
            try:
                detail_res = requests.get(link, headers=HEADERS, timeout=10)
                html = detail_res.text
                
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
                    print(f"    [+] [BOLA] {title} -> {valid_stream}")

            except Exception:
                continue

        output_file = "livetv_soccer.m3u"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(m3u_content)

        print(f"\n[+] Selesai! {count} stream murni sepak bola tersimpan di {output_file}")

    except Exception as e:
        print(f"[X] Error: {e}")

if __name__ == "__main__":
    main()
