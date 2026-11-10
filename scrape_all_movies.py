import html
import json
import os
import re
import time
import random
from concurrent.futures import ThreadPoolExecutor
import requests

# DAFTAR URL TARGET (TERMASUK URL CUSTOM DARI PIYAN)
BASE_URLS = [
    "https://new1.pusatfilm21info.com/movie?sort=latest", # Semua film urutan paling baru
    "https://new1.pusatfilm21info.com/movie?sort=latest&country=indonesia", # Film Indonesia terbaru
    "https://new1.pusatfilm21info.com/movie?sort=latest&genre=horror&country=indonesia", # Horor Indonesia terbaru
    "https://new1.pusatfilm21info.com/movie",
    "https://new1.pusatfilm21info.com/tv",
    "https://new1.pusatfilm21info.com/genre/action",
    "https://new1.pusatfilm21info.com/genre/horror",
    "https://new1.pusatfilm21info.com/genre/comedy"
]

START_PAGE = 1
END_PAGE = 10  # Batas maksimal halaman PER KATEGORI

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
        ' like Gecko) Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept': (
        'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
    ),
    'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://new1.pusatfilm21info.com/',
}

# DAFTAR BLACKLIST DOMAIN IKLAN / POP-UNDER / TRACKING
AD_DOMAINS = [
    'decafeligiblyhad', 'adsterra', 'popads', 'histats', 'bet365', 
    'slot', 'gacor', 'doubleclick', 'analytics', 'greentrafsa', 
    'smartpop', 'trafsa', 'clickadu', 'propellerads', 'exoclick'
]

def process_single_movie(movie_url):
    """
    Fungsi andalan untuk mengekstrak data film dengan presisi tinggi.
    """
    try:
        res = requests.get(movie_url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return None

        content_type = "series" if "/tv/" in movie_url or "/episode/" in movie_url else "movie"

        # 1. Judul & Tahun
        title_match = re.search(r'<meta property="og:title" content="([^"]+)"', res.text)
        if title_match:
            raw_title = title_match.group(1)
        else:
            h1_match = re.search(r'<h1[^>]*>(.+?)</h1>', res.text, re.DOTALL)
            raw_title = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip() if h1_match else 'Unknown Title'

        year_match = re.search(r'\((\d{4})\)', raw_title)
        year = year_match.group(1) if year_match else ''

        title = re.sub(r'(?i)(Nonton\s*Film|Nonton|Sub\s*Indo|Streaming|/.*PUSATFILM21|\(\d{4}\))', '', raw_title).strip()
        title = html.unescape(title)

        # 2. Rating Akurat
        rating = '0.0'
        json_rating = re.search(r'"ratingValue"\s*:\s*"?(\d+\.\d+)', res.text)
        if json_rating:
            rating = json_rating.group(1)
        else:
            rating_match = re.search(r'★\s*(\d+\.\d+)', res.text)
            if not rating_match:
                rating_match = re.search(r'(?:Rating|rating|imdb)[^\d]*(\d+\.\d+)', res.text, re.IGNORECASE)
            if rating_match:
                rating = rating_match.group(1)

        # 3. Poster
        poster_match = re.search(r'<meta property="og:image" content="([^"]+)"', res.text)
        poster = poster_match.group(1) if poster_match else ''

        # 4. Genre Bersih
        genre_slugs = re.findall(r'href=[\'"](?:https?://[^\'"]+)?/genre/([a-zA-Z0-9-]+)/?[\'"]', res.text)
        genres = [g.replace('-', ' ').title() for g in set(genre_slugs)] if genre_slugs else ['Movie']

        # 5. Sinopsis Murni
        syn_match = re.search(r'<meta (?:property="og:description"|name="description") content="([^"]+)"', res.text, re.IGNORECASE)
        raw_synopsis = syn_match.group(1) if syn_match else ""
        synopsis = re.sub(r'(?i)Nonton\s+.*?(?:PUSATFILM21|subtitle Indonesia).*?(?:\.|$)', '', raw_synopsis).strip()
        synopsis = html.unescape(synopsis)

        # 6. Metadata Lainnya
        country, cast, duration, director = '', '', '', ''
        seo_match = re.search(r'(Film\s+[^<]+?dari\s+[^<]+?disutradarai[^<]+)', res.text, re.IGNORECASE)
        if seo_match:
            seo_text = seo_match.group(1)
            c_match = re.search(r'dari\s+([A-Z][a-zA-Z\s]+?)\s+ini', seo_text)
            if c_match: country = c_match.group(1).strip()
            dir_match = re.search(r'disutradarai\s+(.+?)\s+dan\s+dibintangi', seo_text)
            if dir_match: director = dir_match.group(1).strip()
            cast_match = re.search(r'dibintangi\s+(.+?)\.', seo_text)
            if cast_match: cast = cast_match.group(1).strip()

        dur_match = re.search(r'Durasi\s+(\d+\s*jam\s*\d*\s*menit|\d+\s*menit)', res.text, re.IGNORECASE)
        if not dur_match:
            dur_match = re.search(r'>\s*(\d+j\s*\d+m|\d+m)\s*<', res.text)
        if dur_match: duration = dur_match.group(1).strip()

        # 7. MULTI-SERVER EXTRACTION (DENGAN FILTER IKLAN SUPER KETAT)
        servers = []
        all_iframes = re.findall(r'<iframe[^>]+src=[\'"](https?://[^\'"]+)[\'"]', res.text)
        all_embeds = re.findall(r'https?://(?:kotakajaib|streamtape|vikingfile|hydrax|gdplayer)[^\s\'"]+', res.text, re.IGNORECASE)

        # Filter: Hanya simpan link iframe yang BUKAN iklan
        clean_iframes = [link for link in all_iframes if not any(ad in link.lower() for ad in AD_DOMAINS)]
        combined_links = list(set(clean_iframes + all_embeds))

        for idx, link in enumerate(combined_links):
            server_name = "Server Utama"
            if "kotakajaib" in link: server_name = "KotakAjaib"
            elif "streamtape" in link: server_name = "Streamtape"
            elif "vikingfile" in link: server_name = "Vikingfile"
            elif "hydrax" in link: server_name = "Hydrax"
            elif "gdplayer" in link: server_name = "GDPlayer"
            else: server_name = f"Server {idx+1}"

            servers.append({"name": server_name, "url": link})

        embed_url = servers[0]["url"] if servers else ""

        if servers or embed_url:
            print(f'[OK] Tersimpan: {title} | Ditemukan {len(servers)} server')
            return {
                'title': title, 'type': content_type, 'year': year, 'rating': rating,
                'duration': duration, 'country': country, 'director': director, 'cast': cast,
                'synopsis': synopsis, 'genres': genres, 'poster': poster, 'url': movie_url,
                'embed_url': embed_url, 'servers': servers
            }
    except Exception:
        pass
    return None

def build_pagination_url(base, page):
    """
    Fungsi cerdas untuk merakit URL pagination.
    """
    if page == 1:
        return base

    if '?' in base:
        parts = base.split('?', 1)
        base_path = parts[0].rstrip('/')
        query_params = parts[1]
        return f"{base_path}/page/{page}/?{query_params}"
    else:
        return f"{base.rstrip('/')}/page/{page}/"

def scrape_pusatfilm():
    movies_data = []
    if os.path.exists('movies.json'):
        with open('movies.json', 'r', encoding='utf-8') as f:
            try: movies_data = json.load(f)
            except: movies_data = []

    # === FITUR OTO-CLEAN: BERSIHKAN SERVER IKLAN DARI DATA EXISTING MOVIES.JSON ===
    print("[*] Memeriksa & membersihkan data movies.json lama dari domain iklan...")
    cleaned_count = 0
    for item in movies_data:
        if 'servers' in item and isinstance(item['servers'], list):
            orig_len = len(item['servers'])
            item['servers'] = [
                s for s in item['servers'] 
                if not any(ad in s.get('url', '').lower() for ad in AD_DOMAINS)
            ]
            if len(item['servers']) < orig_len:
                cleaned_count += 1
                if item['servers']:
                    item['embed_url'] = item['servers'][0]['url']
                else:
                    item['embed_url'] = ""

    if cleaned_count > 0:
        print(f"[✓] Berhasil menyapu server iklan dari {cleaned_count} film lama!")

    processed_urls = {item.get('url') for item in movies_data if 'url' in item}

    print(f"\n[+] Memulai Scraping Multi-Kategori (Maks {END_PAGE} Halaman/Kategori)...")

    # OUTER LOOP: Mengunjungi setiap Kategori / Base URL
    for base_url in BASE_URLS:
        print(f"\n==================================================")
        print(f"[>] MEMASUKI KATEGORI: {base_url}")
        print(f"==================================================")

        # INNER LOOP: Pindah Halaman di dalam kategori tersebut
        for page in range(START_PAGE, END_PAGE + 1):
            url = build_pagination_url(base_url, page)
            print(f"\n[->] Memindai Halaman {page}: {url}")

            try:
                res = requests.get(url, headers=HEADERS, timeout=15)

                if res.status_code == 404:
                    print(f"[!] Halaman {page} tidak ditemukan (404). Kategori ini sudah habis ditelusuri.")
                    break 

                if res.status_code != 200:
                    print(f"[!] Gagal dimuat (Status: {res.status_code}). Lanjut halaman berikutnya...")
                    continue

                movie_links = re.findall(
                    r'href=[\'"](https?://new1\.pusatfilm21info\.com/(?:movie|tv|episode)/[^\'"]+)[\'"]',
                    res.text,
                )
                if not movie_links:
                    movie_links = re.findall(r'href=[\'"](/(?:movie|tv|episode)/[^\'"]+)[\'"]', res.text)
                    movie_links = [f'https://new1.pusatfilm21info.com{l}' for l in movie_links]

                valid_links = [l for l in set(movie_links) if '/page/' not in l]
                unprocessed_urls = [l for l in valid_links if l not in processed_urls]

                if not unprocessed_urls:
                    print(f"[*] Tidak ada film baru di halaman {page}. (Sudah ada di JSON)")
                else:
                    print(f"[*] Ditemukan {len(unprocessed_urls)} link baru. Mengekstrak data secara paralel...")

                    with ThreadPoolExecutor(max_workers=5) as executor:
                        results = list(executor.map(process_single_movie, unprocessed_urls))

                    added = 0
                    for item in results:
                        if item:
                            # Masukkan ke posisi paling depan (index 0) agar muncul paling kiri di aplikasi
                            movies_data.insert(0, item)
                            processed_urls.add(item['url'])
                            added += 1

                    # Simpan dalam format minified (tanpa spasi/enter) agar ukuran file sangat kecil & ringan
                    with open('movies.json', 'w', encoding='utf-8') as f:
                        json.dump(movies_data, f, ensure_ascii=False, separators=(',', ':'))

                    print(f"[+] Halaman {page} selesai. {added} data baru ditambahkan ke posisi terdepan movies.json.")

            except Exception as e:
                print(f'[-] Error saat memproses halaman {page}: {e}')

            # ANTI-BLOCKING DELAY
            delay = random.uniform(1.5, 3.5)
            print(f"[*] Jeda aman {delay:.2f} detik agar tidak diblokir...")
            time.sleep(delay)

    # Simpan versi final
    with open('movies.json', 'w', encoding='utf-8') as f:
        json.dump(movies_data, f, ensure_ascii=False, separators=(',', ':'))

    print(f'\n[v] MISI SELESAI! Total keseluruhan: {len(movies_data)} film/series tersimpan bersih.')

if __name__ == '__main__':
    scrape_pusatfilm()
