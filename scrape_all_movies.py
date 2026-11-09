import base64
import json
import os
import re
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


def process_single_movie(movie_url):
  """Memproses 1 film secara paralel"""
  try:
    res = requests.get(movie_url, headers=HEADERS, timeout=8)
    if res.status_code != 200:
      return None
    match = re.search(
        r'src=[\'"](https?://playsobat\.xyz/e/[^\'"]+)[\'"]', res.text
    )
    if not match:
      return None

    embed_url = match.group(1)
    embed_res = requests.get(
        embed_url,
        headers={**HEADERS, 'Referer': 'https://154.203.167.130/'},
        timeout=8,
    )
    player_json = decrypt_player_payload(embed_res.text)

    if player_json:
      print(f'[OK] Sukses: {movie_url}')
      return {
          'url': movie_url,
          'embed_url': embed_url,
          'players': player_json,
      }
  except Exception:
    pass
  return None


def scrape_rebahin(start_page=1, max_pages=1):
  movies_data = []
  if os.path.exists('movies.json'):
    with open('movies.json', 'r', encoding='utf-8') as f:
      try:
        movies_data = json.load(f)
      except Exception:
        movies_data = []

  processed_urls = {item.get('url') for item in movies_data if 'url' in item}

  for page in range(start_page, max_pages + 1):
    catalog_url = f'https://154.203.167.130/page/{page}/'
    try:
      res = requests.get(catalog_url, headers=HEADERS, timeout=8)
      if res.status_code != 200:
        break

      movie_links = set(
          re.findall(
              r'href=[\'"](https?://154\.203\.167\.130/[^/\'"]+/?)[\'"]',
              res.text,
          )
      )
      unprocessed = [
          link
          for link in movie_links
          if link not in processed_urls
          and not any(
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

      print(
          f'[+] Memproses {len(unprocessed)} film di halaman {page} secara'
          ' paralel...'
      )

      # Eksekusi 5 request film sekaligus secara paralel
      with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_single_movie, unprocessed))

      for item in results:
        if item:
          movies_data.append(item)
          processed_urls.add(item['url'])

    except Exception as e:
      print(f'[-] Error halaman {page}: {e}')

  with open('movies.json', 'w', encoding='utf-8') as f:
    json.dump(movies_data, f, indent=2)
  print('[v] movies.json berhasil diperbarui!')


if __name__ == '__main__':
  # Untuk update rutin GitHub Actions, cukup max_pages=1
  scrape_rebahin(start_page=1, max_pages=1)
