import base64
import json
import os
import re
import time
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
  """Dekripsi window.payload dari HTML embed playsobat.xyz"""
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
  except Exception as e:
    print(f'[-] Dekripsi gagal: {e}')
    return None


def get_embed_url(movie_url):
  """Ambil link embed playsobat dari halaman detail film"""
  try:
    res = requests.get(movie_url, headers=HEADERS, timeout=10)
    if res.status_code != 200:
      return None

    match = re.search(
        r'src=[\'"](https?://playsobat\.xyz/e/[^\'"]+)[\'"]', res.text
    )
    if match:
      return match.group(1)
  except Exception as e:
    print(f'[-] Gagal membuka detail film: {e}')
    return None


def scrape_rebahin(start_page=1, max_pages=3):
  movies_data = []

  # Load data lama jika ada
  if os.path.exists('movies.json'):
    with open('movies.json', 'r', encoding='utf-8') as f:
      try:
        movies_data = json.load(f)
      except Exception:
        movies_data = []

  processed_urls = {item.get('url') for item in movies_data if 'url' in item}

  for page in range(start_page, max_pages + 1):
    catalog_url = f'https://154.203.167.130/page/{page}/'
    print(f'\n[+] Memindai Katalog Halaman {page}: {catalog_url}')

    try:
      res = requests.get(catalog_url, headers=HEADERS, timeout=10)
      if res.status_code != 200:
        print(f'[-] Halaman {page} tidak ditemukan. Berhenti.')
        break

      movie_links = set(
          re.findall(
              r'href=[\'"](https?://154\.203\.167\.130/[^/\'"]+/?)[\'"]',
              res.text,
          )
      )

      filtered_links = [
          link
          for link in movie_links
          if not any(
              x in link
              for x in [
                  '/page/',
                  '/category/',
                  '/genre/',
                  '/country/',
                  '/year/',
                  '/wp-',
              ]
          )
      ]

      print(f'[>] Ditemukan {len(filtered_links)} link film di halaman {page}')

      for movie_url in filtered_links:
        if movie_url in processed_urls:
          print(f'[=] Melewati: {movie_url}')
          continue

        print(f'  [->] Memproses: {movie_url}')
        embed_url = get_embed_url(movie_url)

        if embed_url:
          embed_res = requests.get(
              embed_url,
              headers={**HEADERS, 'Referer': 'https://154.203.167.130/'},
              timeout=10,
          )
          player_json = decrypt_player_payload(embed_res.text)

          if player_json:
            movie_entry = {
                'url': movie_url,
                'embed_url': embed_url,
                'players': player_json,
            }
            movies_data.append(movie_entry)
            processed_urls.add(movie_url)
            print(
                '      [OK] Sukses dekripsi player:'
                f' {list(player_json.keys())}'
            )

        time.sleep(2)

      with open('movies.json', 'w', encoding='utf-8') as f:
        json.dump(movies_data, f, indent=2)
      print(f'[v] Progress halaman {page} disimpan ke movies.json')

    except Exception as e:
      print(f'[-] Error halaman {page}: {e}')

    time.sleep(3)


if __name__ == '__main__':
  scrape_rebahin(start_page=1, max_pages=3)
