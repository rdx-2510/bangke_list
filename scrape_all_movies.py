import base64
import html
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import requests

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
        ' like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )
}
AES_KEY = b'96fb393f57087e9333cc067bf4aa378e'


def decrypt_player_payload(html_content):
  """Mendekripsi payload AES-CBC dari playsobat.xyz"""
  match = re.search(
      r'window\.payload\s*=\s*("(?:[^"\\]|\\.)*")', html_content
  )
  if not match:
    return None
  try:
    json_str = json.loads(match.group(1))
    payload = json.loads(json_str)
    iv = base64.b64decode(payload['iv'])
    ciphertext = base64.b64decode(payload['data'])
    cipher = AES.new(AES_KEY, AES.MODE_CBC, iv)
    decrypted_bytes = unpad(cipher.decrypt(ciphertext), AES.block_size)
    return json.loads(decrypted_bytes.decode('utf-8'))
  except Exception:
    return None


def process_single_movie(movie_item):
  """Memproses 1 film: Judul, Poster, Rating, Genre, Embed, & Players"""
  movie_url = movie_item['url']
  raw_rating = movie_item['rating']

  try:
    res = requests.get(movie_url, headers=HEADERS, timeout=15)
    if res.status_code != 200:
      return None

    # 1. Ekstrak & Bersihkan Judul Film dari Spam SEO
    h1_match = re.search(
        r'<h1[^>]*class="entry-title"[^>]*>(.+?)</h1>', res.text, re.DOTALL
    )
    if h1_match:
      raw_title = re.sub(r'<[^>]+>', '', h1_match.group(1)).strip()
    else:
      title_match = re.search(
          r'<meta property="og:title" content="([^"]+)"', res.text
      )
      raw_title = title_match.group(1) if title_match else 'Unknown Title'

    title = re.sub(
        r'(?i)(REBAHINXXI|LK21|LAYARKACA21|REBAHIN|BIOSKOPKEREN|Nonton'
        r' Film|Sub Indo|Streaming|\s*-\s*154\.203\.167\.130)',
        '',
        raw_title,
    ).strip()
    title = html.unescape(title)

    # 2. Ekstrak Poster Film Asli
    poster = ''
    poster_match = re.search(
        r'<figure[^>]*class="pull-left"[^>]*>.*?<img[^>]*src="([^"]+)"',
        res.text,
        re.DOTALL,
    )
    if poster_match:
      poster = poster_match.group(1)
    else:
      images = re.findall(r'<img[^>]*src="([^"]+)"', res.text)
      for img in images:
        if 'cropped-ikonatas' not in img and (
            'playsobat' in img or 'uploads' in img
        ):
          poster = img
          break

    # 3. Ekstrak Genre / Kategori dari Halaman Detail
    genre_matches = re.findall(
        r'href=[\'"]https?://154\.203\.167\.130/genre/([^\'"]+)/?[\'"]', res.text
    )
    genres = (
        [g.replace('-', ' ').title() for g in set(genre_matches)]
        if genre_matches
        else ['Movie']
    )

    # 4. Ambil Embed URL Playsobat & Dekripsi Player Servers
    embed_match = re.search(
        r'src=[\'"](https?://playsobat\.xyz/e/[^\'"]+)[\'"]', res.text
    )
    if not embed_match:
      return None

    embed_url = embed_match.group(1)
    embed_res = requests.get(
        embed_url,
        headers={**HEADERS, 'Referer': 'https://154.203.167.130/'},
        timeout=15,
    )
    player_json = decrypt_player_payload(embed_res.text)

    if player_json:
      print(f'[OK] Sukses: {title} | Rating: {raw_rating} | Genre: {genres}')
      return {
          'title': title,
          'rating': raw_rating,
          'genres': genres,
          'poster': poster,
          'url': movie_url,
          'embed_url': embed_url,
          'players': player_json,
      }
  except Exception:
    pass
  return None


def scrape_rebahin(start_page=1, max_pages=50):
  movies_data = []

  if os.path.exists('movies.json'):
    with open('movies.json', 'r', encoding='utf-8') as f:
      try:
        movies_data = json.load(f)
      except Exception:
        movies_data = []

  processed_urls = {
      item.get('url')
      for item in movies_data
      if 'url' in item
      and 'title' in item
      and item.get('title') != ''
      and '&amp;' not in item.get('title')
  }

  for page in range(start_page, max_pages + 1):
    catalog_url = f'https://154.203.167.130/page/{page}/'
    print(f'\n[+] Memindai Katalog Halaman {page}/{max_pages}...')

    try:
      res = requests.get(catalog_url, headers=HEADERS, timeout=15)
      if res.status_code != 200:
        print(f'[-] Halaman {page} tidak ditemukan atau habis. Berhenti.')
        break

      # Ekstrak card film beserta rating dari halaman katalog utama menggunakan Regex presisi
      # Mencari blok kartu film yang memuat rating bintang dan URL film
      card_pattern = r'<div[^>]*class="[^"]*search-item[^"]*"[^>]*>.*?</div>\s*</div>'
      # Cara aman: Cari semua link film beserta rating di sekitarnya
      items_to_process = []

      # Parsing sederhana per baris/kartu dari HTML katalog
      # Mencari pola rating bintang: ⭐ 7.18 atau ★ 5
      raw_cards = res.text.split('class="search-item"')
      for card in raw_cards:
        link_match = re.search(
            r'href=[\'"](https?://154\.203\.167\.130/[^/\'"]+/?)[^>]*[\'"]',
            card,
        )
        if not link_match:
          continue

        link = link_match.group(1)
        if any(
            x in link
            for x in [
                '/page/',
                '/category/',
                '/genre/',
                '/country/',
                '/year/',
                '/wp-',
            ]
        ):
          continue

        if link in processed_urls:
          continue

        # Ambil rating dari kartu katalog
        rating_match = re.search(r'★\s*([\d\.]+)', card)
        rating = rating_match.group(1) if rating_match else '0.0'

        items_to_process.append({'url': link, 'rating': rating})

      # Hapus duplikat URL
      unique_items = {item['url']: item for item in items_to_process}.values()
      unprocessed = list(unique_items)

      if not unprocessed:
        print(f'[=] Semua film di halaman {page} sudah ada di database.')
        continue

      print(
          f'[>] Memproses {len(unprocessed)} film baru di halaman {page} secara'
          ' paralel (Safe Mode)...'
      )

      with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(process_single_movie, unprocessed))

      for item in results:
        if item:
          movies_data.append(item)
          processed_urls.add(item['url'])

      with open('movies.json', 'w', encoding='utf-8') as f:
        json.dump(movies_data, f, indent=2, ensure_ascii=False)

      time.sleep(2)

    except Exception as e:
      print(f'[-] Error timeout/koneksi pada halaman {page}: {e}')
      time.sleep(3)

  print(f'\n[v] SELESAI! Total {len(movies_data)} film tersimpan di movies.json')


if __name__ == '__main__':
  scrape_rebahin(start_page=1, max_pages=50)
