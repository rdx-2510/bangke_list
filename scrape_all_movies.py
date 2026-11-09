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

    # Ambil tahun dari judul (misal: "Heart of the Beast (2026)")
    year_match = re.search(r'\((\d{4})\)', raw_title)
    year = year_match.group(1) if year_match else ''

    title = re.sub(
        r'(?i)(Nonton\s*Film|Nonton|Sub\s*Indo|Streaming|/.*PUSATFILM21|\(\d{4}\))',
        '',
        raw_title,
    ).strip()
    title = html.unescape(title)

    # 2. Rating Dinamis Asli
    rating_match = re.search(r'★\s*([\d\.]+)', res.text)
    if not rating_match:
        rating_match = re.search(r'(?:Rating|rating)[^\d]*([\d\.]+)', res.text)
    rating = rating_match.group(1) if rating_match else '0.0'

    # 3. Poster
    poster_match = re.search(
        r'<meta property="og:image" content="([^"]+)"', res.text
    )
    poster = poster_match.group(1) if poster_match else ''

    # 4. Ekstrak Genre Bersih
    genre_slugs = re.findall(
        r'href=[\'"](?:https?://[^\'"]+)?/genre/([a-zA-Z0-9-]+)/?[\'"]', 
        res.text
    )
    if genre_slugs:
      genres = [g.replace('-', ' ').title() for g in set(genre_slugs)]
    else:
      genres = ['Movie']

    # 5. Ekstrak Sinopsis, Negara, Pemeran, dan Durasi
    synopsis_paragraphs = []
    country = ''
    cast = ''
    duration = ''
    director = ''

    # Mengambil semua teks di dalam tag paragraf <p>
    paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', res.text, re.DOTALL | re.IGNORECASE)
    for p in paragraphs:
        # Bersihkan tag HTML di dalam paragraf
        clean_text = re.sub(r'<[^>]+>', '', p).strip()
        clean_text = html.unescape(clean_text)
        if not clean_text: 
            continue
            
        # Deteksi apakah ini paragraf informasi SEO (biasanya diawali "Nonton...")
        if clean_text.lower().startswith('nonton ') and 'disutradarai' in clean_text.lower():
            # Tangkap Negara
            c_match = re.search(r'dari\s+([A-Z][a-zA-Z\s]+?)\s+ini\s+disutradarai', clean_text)
            if c_match: country = c_match.group(1).strip()
            
            # Tangkap Sutradara
            dir_match = re.search(r'disutradarai\s+(.+?)\s+dan\s+dibintangi', clean_text)
            if dir_match: director = dir_match.group(1).strip()
            
            # Tangkap Pemeran (Cast)
            cast_match = re.search(r'dibintangi\s+(.+?)\.\s*Durasi', clean_text)
            if cast_match: cast = cast_match.group(1).strip()
            
            # Tangkap Durasi
            dur_match = re.search(r'Durasi\s+([^,]+)', clean_text)
            if dur_match: duration = dur_match.group(1).strip()
        else:
            # Jika bukan paragraf data, berarti ini adalah Sinopsis cerita
            synopsis_paragraphs.append(clean_text)

    synopsis = '\n\n'.join(synopsis_paragraphs)

    # 6. Embed KotakAjaib
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
      print(f'[OK] Sukses: {title} | Rating: {rating} | Negara: {country} | Durasi: {duration}')
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


def scrape_pusatfilm(start_page=1, max_pages=10):
  movies_data = []

  if os.path.exists('movies.json'):
    with open('movies.json', 'r', encoding='utf-8') as f:
      try:
        movies_data = json.load(f)
      except Exception:
        movies_data = []

  processed_urls = {item.get('url') for item in movies_data if 'url' in item}

  # Loop pemindaian multi-halaman
  for page in range(start_page, max_pages + 1):
    if page == 1:
        target_urls = ['https://new1.pusatfilm21info.com/movie/', 'https://new1.pusatfilm21info.com/']
    else:
        target_urls = [f'https://new1.pusatfilm21info.com/movie/page/{page}/', f'https://new1.pusatfilm21info.com/page/{page}/']
    
    res = None
    for url in target_urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                res = r
                print(f'\n[+] Memindai Katalog: {url}')
                break
        except Exception:
            pass
            
    if not res or res.status_code != 200:
        print(f'[-] Halaman {page} tidak ditemukan (404). Berhenti memindai halaman selanjutnya.')
        break

    movie_links = re.findall(
        r'href=[\'"](https?://new1\.pusatfilm21info\.com/movie/[^\'"]+)[\'"]',
        res.text,
    )
    if not movie_links:
      movie_links = re.findall(r'href=[\'"](/movie/[^\'"]+)[\'"]', res.text)
      movie_links = [f'https://new1.pusatfilm21info.com{l}' for l in movie_links]

    unprocessed_urls = [link for link in set(movie_links) if link not in processed_urls]
    print(f'[>] Ditemukan {len(unprocessed_urls)} film baru di Halaman {page}. Memproses...')

    if unprocessed_urls:
      with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(process_single_movie, unprocessed_urls))

      for item in results:
        if item:
          movies_data.append(item)
          processed_urls.add(item['url'])

      # Auto-save setiap selesai 1 halaman
      with open('movies.json', 'w', encoding='utf-8') as f:
        json.dump(movies_data, f, indent=2, ensure_ascii=False)

    time.sleep(2) 

  print(f'\n[v] SELESAI! Total {len(movies_data)} film tersimpan di movies.json')


if __name__ == '__main__':
  # Menyedot dari halaman 1 sampai 10 secara otomatis
  scrape_pusatfilm(start_page=1, max_pages=10)
