import html
import json
import os
import re
import time
import random
from concurrent.futures import ThreadPoolExecutor
import requests

# === KONFIGURASI TMDB UNTUK POSTER & RATING ASLI ===
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OUTPUT_FILE = "pelem.json"

# DAFTAR URL TARGET
BASE_URLS = [
    "https://new1.pusatfilm21info.com/movie?sort=latest",
    "https://new1.pusatfilm21info.com/movie?sort=latest&country=indonesia",
    "https://new1.pusatfilm21info.com/movie?sort=latest&genre=horror&country=indonesia",
    "https://new1.pusatfilm21info.com/movie",
    "https://new1.pusatfilm21info.com/series",
    "https://new1.pusatfilm21info.com/genre/action",
    "https://new1.pusatfilm21info.com/genre/horror",
    "https://new1.pusatfilm21info.com/genre/comedy",
    "https://new1.pusatfilm21info.com/network/netflix"
]

START_PAGE = 1
END_PAGE = 10

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

AD_DOMAINS = [
    'decafeligiblyhad', 'adsterra', 'popads', 'histats', 'bet365',
    'slot', 'gacor', 'doubleclick', 'analytics', 'greentrafsa',
    'smartpop', 'trafsa', 'clickadu', 'propellerads', 'exoclick'
]


def fetch_tmdb_details(title, year="", is_tv=False):
    """
    Mencari poster & rating asli dari TMDb dengan toleransi perbedaan tahun rilis.
    Mengembalikan tuple: (poster_url, rating_str)
    """
    if not TMDB_API_KEY or TMDB_API_KEY == "MASUKKAN_API_KEY_TMDB_KAMU_DISINI":
        return "", ""

    clean_title = re.sub(r'(?i)(Season \d+|Episode \d+)', '', title).strip()
    search_type = "tv" if is_tv else "movie"
    base_search_url = (
        f"https://api.themoviedb.org/3/search/{search_type}"
        f"?api_key={TMDB_API_KEY}&query={requests.utils.quote(clean_title)}"
    )

    url_with_year = base_search_url
    if year:
        year_param = "first_air_date_year" if is_tv else "primary_release_year"
        url_with_year += f"&{year_param}={year}"

    def extract_info(result_item):
        poster_path = result_item.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""
        vote_avg = result_item.get("vote_average")
        rating_str = ""
        try:
            if vote_avg is not None and float(vote_avg) > 0:
                rating_str = f"{float(vote_avg):.1f}"
        except Exception:
            pass
        return poster_url, rating_str

    try:
        res = requests.get(url_with_year, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get("results"):
                return extract_info(data["results"][0])

        if year:
            res_no_year = requests.get(base_search_url, timeout=5)
            if res_no_year.status_code == 200:
                data_no = res_no_year.json()
                if data_no.get("results"):
                    return extract_info(data_no["results"][0])

    except Exception:
        pass

    return "", ""


def process_single_movie(movie_url):
    if not movie_url or not str(movie_url).startswith("http"):
        return None
    try:
        res = requests.get(movie_url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return None

        content_type = "series" if "/tv/" in movie_url or "/episode/" in movie_url else "movie"

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

        poster_match = re.search(r'<meta property="og:image" content="([^"]+)"', res.text)
        original_poster = poster_match.group(1) if poster_match else ''

        tmdb_poster, tmdb_rating = fetch_tmdb_details(title, year, content_type == "series")
        final_poster = tmdb_poster if tmdb_poster else original_poster

        # Prioritaskan rating dari TMDb; fallback ke IMDb di halaman web (abaikan rating widget 1.5)
        rating = tmdb_rating if tmdb_rating else '0.0'
        if rating == '0.0':
            imdb_match = re.search(r'(?:imdb|IMDb)[^\d]{0,15}(\d+\.\d+)', res.text)
            if imdb_match and imdb_match.group(1) != '1.5':
                rating = imdb_match.group(1)

        genre_slugs = re.findall(r'href=[\'"](?:https?://[^\'"]+)?/genre/([a-zA-Z0-9-]+)/?[\'"]', res.text)
        genres = [g.replace('-', ' ').title() for g in set(genre_slugs)] if genre_slugs else ['Movie']

        syn_match = re.search(r'<meta (?:property="og:description"|name="description") content="([^"]+)"', res.text, re.IGNORECASE)
        raw_synopsis = syn_match.group(1) if syn_match else ""
        synopsis = re.sub(r'(?i)Nonton\s+.*?(?:PUSATFILM21|subtitle Indonesia).*?(?:\.|$)', '', raw_synopsis).strip()
        synopsis = html.unescape(synopsis)

        country, cast, duration, director = '', '', '', ''
        seo_match = re.search(r'(Film\s+[^<]+?dari\s+[^<]+?disutradarai[^<]+)', res.text, re.IGNORECASE)
        if seo_match:
            seo_text = seo_match.group(1)
            c_match = re.search(r'dari\s+([A-Z][a-zA-Z\s]+?)\s+ini', seo_text)
            if c_match:
                country = c_match.group(1).strip()
            dir_match = re.search(r'disutradarai\s+(.+?)\s+dan\s+dibintangi', seo_text)
            if dir_match:
                director = dir_match.group(1).strip()
            cast_match = re.search(r'dibintangi\s+(.+?)\.', seo_text)
            if cast_match:
                cast = cast_match.group(1).strip()

        dur_match = re.search(r'Durasi\s+(\d+\s*jam\s*\d*\s*menit|\d+\s*menit)', res.text, re.IGNORECASE)
        if not dur_match:
            dur_match = re.search(r'>\s*(\d+j\s*\d+m|\d+m)\s*<', res.text)
        if dur_match:
            duration = dur_match.group(1).strip()

        servers = []
        all_iframes = re.findall(r'<iframe[^>]+src=[\'"](https?://[^\'"]+)[\'"]', res.text)
        all_embeds = re.findall(r'https?://(?:kotakajaib|streamtape|vikingfile|hydrax|gdplayer)[^\s\'"]+', res.text, re.IGNORECASE)

        clean_iframes = [link for link in all_iframes if not any(ad in link.lower() for ad in AD_DOMAINS)]
        combined_links = list(set(clean_iframes + all_embeds))

        for idx, link in enumerate(combined_links):
            server_name = "Server Utama"
            if "kotakajaib" in link:
                server_name = "KotakAjaib"
            elif "streamtape" in link:
                server_name = "Streamtape"
            elif "vikingfile" in link:
                server_name = "Vikingfile"
            elif "hydrax" in link:
                server_name = "Hydrax"
            elif "gdplayer" in link:
                server_name = "GDPlayer"
            else:
                server_name = f"Server {idx+1}"

            servers.append({"name": server_name, "url": link})

        embed_url = servers[0]["url"] if servers else ""

        if servers or embed_url:
            status_poster = "TMDb" if tmdb_poster else "Web/Thumbnail"
            print(f'[OK] Tersimpan: {title} | Rating: {rating} | Server: {len(servers)} | Poster: {status_poster}')
            return {
                'title': title, 'type': content_type, 'year': year, 'rating': rating,
                'duration': duration, 'country': country, 'director': director, 'cast': cast,
                'synopsis': synopsis, 'genres': genres, 'poster': final_poster, 'url': movie_url,
                'embed_url': embed_url, 'servers': servers
            }
    except Exception:
        pass
    return None


def build_pagination_url(base, page):
    """
    Format pagination WordPress: menyisipkan /page/{page}/ sebelum query string (?)
    Contoh: .../movie?sort=latest -> .../movie/page/2/?sort=latest
    """
    if page == 1:
        return base
    if '?' in base:
        path, query = base.split('?', 1)
        return f"{path.rstrip('/')}/page/{page}/?{query}"
    return f"{base.rstrip('/')}/page/{page}/"


def scrape_pusatfilm():
    movies_data = []
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            try:
                movies_data = json.load(f)
            except Exception:
                movies_data = []

    if not movies_data and os.path.exists('movies.json'):
        with open('movies.json', 'r', encoding='utf-8') as f:
            try:
                movies_data = json.load(f)
            except Exception:
                movies_data = []

    movies_data = [m for m in movies_data if m.get('url')]

    # === PROSES & SUNTIKKAN MANUAL DARI manual_movies.json ===
    manual_category_map = {}
    if os.path.exists('manual_movies.json'):
        try:
            with open('manual_movies.json', 'r', encoding='utf-8') as mf:
                manual_movies = json.load(mf)
                for mm in manual_movies:
                    m_url = (mm.get('url') or mm.get('stream_url') or '').strip()
                    if m_url.startswith('http'):
                        manual_category_map[m_url] = mm.get('category', 'Film India Jadul')

                existing_urls = {m.get('url') for m in movies_data}
                urls_to_scrape = [u for u in manual_category_map if u not in existing_urls]

                if urls_to_scrape:
                    print(f"[*] Mengambil poster TMDb & link player untuk {len(urls_to_scrape)} film dari manual_movies.json...")
                    with ThreadPoolExecutor(max_workers=5) as executor:
                        manual_results = list(executor.map(process_single_movie, urls_to_scrape))

                    injected_count = 0
                    for item in manual_results:
                        if item:
                            cat = manual_category_map.get(item['url'], 'Film India Jadul')
                            if cat not in item['genres']:
                                item['genres'].insert(0, cat)
                            movies_data.append(item)
                            injected_count += 1
                    print(f"[✓] Berhasil menyuntikkan {injected_count} film lengkap dengan poster & server dari manual_movies.json!")

                for m in movies_data:
                    u = m.get('url')
                    if u in manual_category_map:
                        cat = manual_category_map[u]
                        if 'genres' not in m or not isinstance(m['genres'], list):
                            m['genres'] = [cat]
                        elif cat not in m['genres']:
                            m['genres'].insert(0, cat)
        except Exception as e:
            print(f"[!] Gagal memproses manual_movies.json: {e}")

    print("[*] Memeriksa & membersihkan server iklan dari data lama...")
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

    print("[*] Memeriksa & mereset poster lama agar diperbarui otomatis ke TMDb...")
    for item in movies_data:
        current_poster = item.get('poster', '')
        if not current_poster or "pusatfilm21" in current_poster or "image.tmdb.org" not in current_poster:
            item['poster'] = ""

    # Perbarui rating film lama yang masih '1.5' atau '0.0' langsung lewat TMDb API
    items_need_rating = [
        item for item in movies_data
        if item.get('rating') in ('', '0.0', '1.5', None) and item.get('title')
    ]
    if items_need_rating:
        print(f"[*] Memperbarui rating TMDb untuk {len(items_need_rating)} film lama...")

        def refresh_tmdb_item(item):
            poster, rating = fetch_tmdb_details(
                item.get('title', ''),
                item.get('year', ''),
                item.get('type') == 'series'
            )
            if rating:
                item['rating'] = rating
            elif item.get('rating') == '1.5':
                item['rating'] = '0.0'
            if poster and not item.get('poster'):
                item['poster'] = poster

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(refresh_tmdb_item, items_need_rating))
        print("[✓] Pembaruan rating film lama selesai.")

    processed_urls = {item.get('url') for item in movies_data if item.get('url')}
    latest_urls_ordered = []

    force_check_urls = [item['url'] for item in movies_data if item.get('url') and not item.get('poster')]
    if force_check_urls:
        print(f"[*] Mencoba memperbarui {len(force_check_urls)} poster yang masih kosong...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            poster_results = list(executor.map(process_single_movie, force_check_urls))
        updated_posters = 0
        for item in poster_results:
            if item and item.get('poster'):
                existing_idx = next((i for i, m in enumerate(movies_data) if m.get('url') == item['url']), -1)
                if existing_idx != -1:
                    movies_data[existing_idx] = item
                    updated_posters += 1
        print(f"[✓] Pembaruan poster selesai ({updated_posters} poster diperbarui).")

    print(f"\n[+] Memulai Scraping Multi-Kategori (Maks {END_PAGE} Halaman/Kategori)...")

    for base_url in BASE_URLS:
        is_latest_source = "sort=latest" in base_url
        seen_in_category = set()
        print(f"\n==================================================")
        print(f"[>] MEMASUKI KATEGORI: {base_url}")
        print(f"==================================================")

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

                valid_links = [l for l in dict.fromkeys(movie_links) if '/page/' not in l]

                new_links_in_cat = [l for l in valid_links if l not in seen_in_category]
                if page > 1 and not new_links_in_cat:
                    print(f"[*] Halaman {page} tidak memuat judul baru (batas halaman/infinite scroll). Lanjut kategori berikutnya.")
                    break
                seen_in_category.update(valid_links)

                if is_latest_source and page <= 3:
                    for l in valid_links:
                        if l not in manual_category_map and l not in latest_urls_ordered:
                            latest_urls_ordered.append(l)

                target_urls = [l for l in valid_links if l not in processed_urls]

                if not target_urls:
                    print(f"[*] Semua film di halaman {page} sudah ada di database.")
                else:
                    print(f"[*] Memproses {len(target_urls)} film baru...")

                    with ThreadPoolExecutor(max_workers=5) as executor:
                        results = list(executor.map(process_single_movie, target_urls))

                    added = 0
                    for item in results:
                        if item:
                            if item['url'] in manual_category_map:
                                cat = manual_category_map[item['url']]
                                if cat not in item['genres']:
                                    item['genres'].insert(0, cat)
                            elif is_latest_source and page <= 3:
                                if 'Film Terbaru' not in item['genres']:
                                    item['genres'].insert(0, 'Film Terbaru')

                            movies_data.insert(0, item)
                            processed_urls.add(item['url'])
                            added += 1

                    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                        json.dump(movies_data, f, ensure_ascii=False, separators=(',', ':'))

                    print(f"[+] Halaman {page} selesai. Menambahkan {added} film baru.")

            except Exception as e:
                print(f'[-] Error saat memproses halaman {page}: {e}')

            delay = random.uniform(1.5, 3.0)
            print(f"[*] Jeda aman {delay:.2f} detik agar tidak diblokir...")
            time.sleep(delay)

    # =========================================================================
    # PENGURUTAN TAMPILAN KATEGORI BANGKETV
    # =========================================================================
    print("\n[*] Mengatur urutan tampilan: Film Terbaru di atas, Film India Jadul di bawah...")
    latest_url_set = set(latest_urls_ordered)
    movie_by_url = {m.get('url'): m for m in movies_data if m.get('url')}

    film_terbaru = []
    seen_terbaru = set()

    for u in latest_urls_ordered:
        if u in movie_by_url and u not in manual_category_map:
            m = movie_by_url[u]
            genres = m.get('genres', [])
            if 'Film Terbaru' in genres:
                genres.remove('Film Terbaru')
            genres.insert(0, 'Film Terbaru')
            m['genres'] = genres
            film_terbaru.append(m)
            seen_terbaru.add(u)

    film_reguler = []
    film_india_jadul = []

    for m in movies_data:
        u = m.get('url')
        if u in seen_terbaru:
            continue

        genres = m.get('genres', [])
        if 'Film India Jadul' in genres or u in manual_category_map:
            if 'Film India Jadul' in genres:
                genres.remove('Film India Jadul')
            genres.insert(0, 'Film India Jadul')
            m['genres'] = genres
            film_india_jadul.append(m)
        else:
            if 'Film Terbaru' in genres and u not in latest_url_set:
                genres.remove('Film Terbaru')
                if not genres:
                    genres = ['Movie']
                m['genres'] = genres
            film_reguler.append(m)

    movies_data = film_terbaru + film_reguler + film_india_jadul

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(movies_data, f, ensure_ascii=False, separators=(',', ':'))

    print(f'\n[v] MISI SELESAI! Total: {len(movies_data)} film (Film Terbaru: {len(film_terbaru)} | Reguler: {len(film_reguler)} | Film India Jadul: {len(film_india_jadul)})')


if __name__ == '__main__':
    scrape_pusatfilm()
