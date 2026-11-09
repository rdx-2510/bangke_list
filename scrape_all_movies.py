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

    # 2. Rating Dinamis Akurat (Mencegah salah tangkap usia 17+ atau titik gantung)
    rating_match = re.search(r'★\s*([0-9]+(?:\.[0-9]+)?)', res.text)
    if not rating_match:
        rating_match = re.search(r'(?:Rating|rating)[^\d]*([0-9]+(?:\.[0-9]+)?)', res.text, re.IGNORECASE)
    rating = rating_match.group(1) if rating_match else '0.0'

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
    if genre_slugs:
      genres = [g.replace('-', ' ').title() for g in set(genre_slugs)]
    else:
      genres = ['Movie']

    # 5. Sinopsis (Murni dari Meta Description agar bebas sampah HTML)
    syn_match = re.search(r'<meta (?:property="og:description"|name="description") content="([^"]+)"', res.text, re.IGNORECASE)
    raw_synopsis = syn_match.group(1) if syn_match else ""
    synopsis = re.sub(r'(?i)Nonton\s+.*?(?:PUSATFILM21|subtitle Indonesia).*?(?:\.|$)', '', raw_synopsis).strip()
    synopsis = html.unescape(synopsis)

    # 6. Metadata Spesifik (Negara, Sutradara, Pemeran, Durasi)
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

    # 7. Embed KotakAjaib
    embed_match = re.search(
        r'https?://kotakajaib\.me/embed/[^\'"]+', res.text
    )
    if not embed_match:
      iframe_match = re.search(
          r'<iframe[^>]+src=[\'"](https?://[^\'"]+)[\'"]', res.text
      )
      embed_url = iframe_match.group(1) if iframe_match else ''
    else:
      embed_url = embed_match.group(0)

    if embed_url:
      print(f'[OK] Sukses: {title} | Rating: {rating} | Durasi: {duration}')
      return {
          'title': title,
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
          'embed_url': embed_url,
      }
  except Exception:
    pass
  return None


def scrape_pusatfilm():
  movies_data = []

  if os.path.exists('movies.json'):
    with open('movies.json', 'r', encoding='utf-8') as f:
      try:
        movies_data = json.load(f)
      except Exception:
        movies_data = []

  processed_urls = {item.get('url') for item in movies_data if 'url' in item}

  # Daftar rute Panen Raya (Beranda + Kategori Populer)
  target_urls = ['https://new1.pusatfilm21info.com/']
  genres = ['action', 'horror', 'comedy', 'thriller', 'drama', 'sci-fi', 'adventure', 'animation', 'romance']
  
  for g in genres:
      target_urls.append(f'https://new1.pusatfilm21info.com/genre/{g}/')
      target_urls.append(f'https://new1.pusatfilm21info.com/genre/{g}/page/2/')

  for catalog_url in target_urls:
    print(f'\n[+] Memindai Katalog: {catalog_url}')
    try:
      res = requests.get(catalog_url, headers=HEADERS, timeout=15)
      if res.status_code != 200:
        print(f'[-] Gagal diakses (Status: {res.status_code}). Lewati.')
        continue

      movie_links = re.findall(
          r'href=[\'"](https?://new1\.pusatfilm21info\.com/movie/[^\'"]+)[\'"]',
          res.text,
      )
      if not movie_links:
        movie_links = re.findall(r'href=[\'"](/movie/[^\'"]+)[\'"]', res.text)
        movie_links = [f'https://new1.pusatfilm21info.com{l}' for l in movie_links]

      # FILTER KRUSIAL: Buang link yang mengandung '/page/' agar bot tidak halusinasi
      valid_links = []
      for link in set(movie_links):
          if '/page/' not in link and link.strip('/') != 'https://new1.pusatfilm21info.com/movie':
              valid_links.append(link)

      unprocessed_urls = [link for link in valid_links if link not in processed_urls]
      print(f'[>] Ditemukan {len(unprocessed_urls)} film baru. Memproses...')

      if unprocessed_urls:
        with ThreadPoolExecutor(max_workers=3) as executor:
          results = list(executor.map(process_single_movie, unprocessed_urls))

        for item in results:
          if item:
            movies_data.append(item)
            processed_urls.add(item['url'])

        # Auto-save setiap selesai 1 rute halaman
        with open('movies.json', 'w', encoding='utf-8') as f:
          json.dump(movies_data, f, indent=2, ensure_ascii=False)

      time.sleep(2) 
    except Exception as e:
      print(f'[-] Error pada {catalog_url}: {e}')

  print(f'\n[v] SELESAI! Total {len(movies_data)} film tersimpan di movies.json')


if __name__ == '__main__':
  scrape_pusatfilm()
