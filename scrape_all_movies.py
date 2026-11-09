import html
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
import requests

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


def process_single_movie(movie_url):
  try:
    res = requests.get(movie_url, headers=HEADERS, timeout=15)
    if res.status_code != 200:
      return None

    content_type = "series" if "/tv/" in movie_url or "/episode/" in movie_url else "movie"

    # 1. Judul & Tahun
    title_match = re.search(
        r'<meta property="og:title" content="([^"]+)"', res.text
    )
    if title_match:
      raw_title = title_match.group(1)
    else:
      h1_match = re.search(r'<h1[^>]*>(.+?)</h1>', res.text, re.DOTALL)
      raw_title = (
          re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
          if h1_match
          else 'Unknown Title'
      )

    year_match = re.search(r'\((\d{4})\)', raw_title)
    year = year_match.group(1) if year_match else ''

    title = re.sub(
        r'(?i)(Nonton\s*Film|Nonton|Sub\s*Indo|Streaming|/.*PUSATFILM21|\(\d{4}\))',
        '',
        raw_title,
    ).strip()
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
    poster_match = re.search(
        r'<meta property="og:image" content="([^"]+)"', res.text
    )
    poster = poster_match.group(1) if poster_match else ''

    # 4. Genre Bersih
    genre_slugs = re.findall(
        r'href=[\'"](?:https?://[^\'"]+)?/genre/([a-zA-Z0-9-]+)/?[\'"]', 
        res.text
    )
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

    # 7. MULTI-SERVER EXTRACTION (Menangkap KotakAjaib, Streamtape, Vikingfile, dll)
    servers = []
    
    # Tangkap semua URL embed atau iframe yang tersedia di halaman
    all_iframes = re.findall(r'<iframe[^>]+src=[\'"](https?://[^\'"]+)[\'"]', res.text)
    all_embeds = re.findall(r'https?://(?:kotakajaib|streamtape|vikingfile|hydrax|gdplayer)[^\s\'"]+', res.text, re.IGNORECASE)
    
    combined_links = list(set(all_iframes + all_embeds))
    
    for idx, link in enumerate(combined_links):
        # Deteksi nama server berdasarkan domainnya
        server_name = "Server Utama"
        if "kotakajaib" in link: server_name = "KotakAjaib"
        elif "streamtape" in link: server_name = "Streamtape"
        elif "vikingfile" in link: server_name = "Vikingfile"
        elif "hydrax" in link: server_name = "Hydrax"
        elif "gdplayer" in link: server_name = "GDPlayer"
        else: server_name = f"Server {idx+1}"
        
        servers.append({
            "name": server_name,
            "url": link
        })

    # Fallback jika tidak ada server multi, ambil embed standar
    embed_url = servers[0]["url"] if servers else ""

    if servers or embed_url:
      print(f'[OK] Sukses: {title} | Ditemukan {len(servers)} pilihan server')
      return {
          'title': title,
          'type': content_type,
          'year': year,
          'rating': rating,
          'duration': duration,
          'country': country,
          'director': director,
          'cast': cast,
          'synopsis': synopsis,
          'genres': genres,
          'poster': poster,
          'url': movie_url,
          'embed_url': embed_url,  # Kompatibilitas mundur
          'servers': servers       # Pilihan banyak server untuk UI mendatang
      }
  except Exception:
    pass
  return None


def scrape_pusatfilm():
  movies_data = []
  if os.path.exists('movies.json'):
    with open('movies.json', 'r', encoding='utf-8') as f:
      try: movies_data = json.load(f)
      except: movies_data = []

  processed_urls = {item.get('url') for item in movies_data if 'url' in item}

  target_urls = [
      'https://new1.pusatfilm21info.com/',
      'https://new1.pusatfilm21info.com/tv/'
  ]
  genres = ['action', 'horror', 'comedy', 'thriller', 'drama', 'sci-fi', 'adventure', 'animation', 'romance']
  for g in genres:
      target_urls.append(f'https://new1.pusatfilm21info.com/genre/{g}/')

  for catalog_url in target_urls:
    print(f'\n[+] Memindai: {catalog_url}')
    try:
      res = requests.get(catalog_url, headers=HEADERS, timeout=15)
      if res.status_code != 200: continue

      movie_links = re.findall(
          r'href=[\'"](https?://new1\.pusatfilm21info\.com/(?:movie|tv|episode)/[^\'"]+)[\'"]',
          res.text,
      )
      if not movie_links:
        movie_links = re.findall(r'href=[\'"](/(?:movie|tv|episode)/[^\'"]+)[\'"]', res.text)
        movie_links = [f'https://new1.pusatfilm21info.com{l}' for l in movie_links]

      valid_links = [l for l in set(movie_links) if '/page/' not in l]
      unprocessed_urls = [l for l in valid_links if l not in processed_urls]

      if unprocessed_urls:
        with ThreadPoolExecutor(max_workers=3) as executor:
          results = list(executor.map(process_single_movie, unprocessed_urls))

        for item in results:
          if item:
            movies_data.append(item)
            processed_urls.add(item['url'])

        with open('movies.json', 'w', encoding='utf-8') as f:
          json.dump(movies_data, f, indent=2, ensure_ascii=False)

      time.sleep(2)
    except Exception as e:
      print(f'[-] Error: {e}')

  print(f'\n[v] SELESAI! Total {len(movies_data)} konten dengan multi-server tersimpan.')


if __name__ == '__main__':
  scrape_pusatfilm()
