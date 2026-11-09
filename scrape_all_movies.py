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


def process_single_movie(movie_item):
  """Memproses 1 film PusatFilm21: Judul, Poster, Rating, Genre, & Embed KotakAjaib"""
  movie_url = movie_item['url']
  raw_rating = movie_item['rating']

  try:
    res = requests.get(movie_url, headers=HEADERS, timeout=15)
    if res.status_code != 200:
      return None

    # 1. Ekstrak & Bersihkan Judul Film
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

    title = re.sub(
        r'(?i)(Nonton\s*Film|Nonton|Sub\s*Indo|Streaming|/.*PUSATFILM21)',
        '',
        raw_title,
    ).strip()
    title = html.unescape(title)

    # 2. Ekstrak Poster Film Asli
    poster_match = re.search(
        r'<meta property="og:image" content="([^"]+)"', res.text
    )
    poster = poster_match.group(1) if poster_match else ''

    # 3. Ekstrak Genre dari Halaman Detail
    genre_matches = re.findall(r'/genre/([^/]+)/?', res.text)
    genres = (
        [g.replace('-', ' ').title() for g in set(genre_matches)]
        if genre_matches
        else ['Movie']
    )

    # 4. Ambil Link Embed Pemutar (KotakAjaib / Iframe)
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
      print(f'[OK] Sukses: {title} | Rating: {raw_rating} | Genre: {genres}')
      return {
          'title': title,
          'rating': raw_rating,
          'genres': genres,
          'poster': poster,
          'url': movie_url,
          'embed_url': embed_url,
      }
  except Exception:
    pass
  return None


def scrape_pusatfilm(start_page=1, max_pages=10):
  movies_data = []

  if os.path.exists('movies.json'):
    with open('movies.json', 'r', encoding='utf-8') as f:
      try:
        movies_data = json.load(f)
      except Exception:
        movies_data = []

  processed_urls = {item.get('url') for item in movies_data if 'url' in item}

  for page in range(start_page, max_pages + 1):
    if page == 1:
      catalog_url = 'https://new1.pusatfilm21info.com/'
    else:
      catalog_url = f'https://new1.pusatfilm21info.com/page/{page}/'

    print(f'\n[+] Memindai Katalog PusatFilm21 Halaman {page}/{max_pages}...')

    try:
      res = requests.get(catalog_url, headers=HEADERS, timeout=15)
      if res.status_code != 200:
        print(
            f'[-] Halaman {page} gagal diakses (Status: {res.status_code}).'
            ' Berhenti.'
        )
        break

      # Ekstrak semua link film dari halaman katalog
      movie_links = re.findall(
          r'href=[\'"](https?://new1\.pusatfilm21info\.com/movie/[^\'"]+)[\'"]',
          res.text,
      )

      items_to_process = []
      for link in set(movie_links):
        if link not in processed_urls:
          items_to_process.append({'url': link, 'rating': '7.0'})

      if not items_to_process:
        print(f'[=] Semua film di halaman {page} sudah up-to-date.')
        continue

      print(
          f'[>] Memproses {len(items_to_process)} film baru di halaman {page}'
          ' secara paralel...'
      )

      with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(process_single_movie, items_to_process))

      for item in results:
        if item:
          movies_data.append(item)
          processed_urls.add(item['url'])

      with open('movies.json', 'w', encoding='utf-8') as f:
        json.dump(movies_data, f, indent=2, ensure_ascii=False)

      time.sleep(2)

    except Exception as e:
      print(f'[-] Error pada halaman {page}: {e}')
      time.sleep(3)

  print(
      f'\n[v] SELESAI! Total {len(movies_data)} film PusatFilm21 tersimpan di'
      ' movies.json'
  )


if __name__ == '__main__':
  scrape_pusatfilm(start_page=1, max_pages=10)
