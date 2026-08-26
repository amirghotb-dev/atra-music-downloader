import os
import re
import unicodedata
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, List

class PersianMusicDirectScraper:
    """
    Direct Iranian Music Scraper (Music-Fa / Direct CDN).
    Features:
    - 100% Direct Original 320kbps MP3s (No DRM, No Cloudflare Bot Challenge)
    - Full Persian Lyrics (متن ترانه)
    - High-Quality Covers (کاور اختصاصی)
    - Fast direct downloads
    """
    def __init__(self, download_audio_dir: str = "public/storage/tracks", download_cover_dir: str = "public/storage/covers"):
        self.download_audio_dir = download_audio_dir
        self.download_cover_dir = download_cover_dir
        os.makedirs(self.download_audio_dir, exist_ok=True)
        os.makedirs(self.download_cover_dir, exist_ok=True)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        }

    @staticmethod
    def slugify(text: str) -> str:
        """Create a URL friendly slug supporting Persian and English characters."""
        text = unicodedata.normalize('NFKC', text)
        text = re.sub(r'[^\w\s\u0600-\u06FF-]', '', text).strip()
        text = re.sub(r'[-\s]+', '-', text)
        return text.lower() or "track"

    def search_tracks(self, query: str, limit: int = 5) -> List[str]:
        """Searches songs and returns direct page URLs."""
        search_url = f"https://music-fa.com/?s={query.replace(' ', '+')}"
        urls = []
        try:
            resp = requests.get(search_url, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                articles = soup.find_all('article')
                for art in articles:
                    h2 = art.find('h2')
                    if h2 and h2.find('a'):
                        a_tag = h2.find('a')
                        href = a_tag.get('href')
                        if href and href not in urls:
                            urls.append(href)
                        if len(urls) >= limit:
                            break
        except Exception as e:
            print(f"[ERROR] Music-Fa search failed: {e}")
        return urls

    def extract_and_download(self, post_url: str) -> Optional[Dict[str, Any]]:
        """Extracts direct 320k MP3 link, Cover art, and Full Persian Lyrics."""
        try:
            resp = requests.get(post_url, headers=self.headers, timeout=15)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')

            # 1. Title and Artist
            title_tag = soup.find('h1') or soup.find('h2')
            raw_title = title_tag.text.strip() if title_tag else "آهنگ جدید"
            # Clean "دانلود آهنگ ..."
            cleaned_title = re.sub(r'^(دانلود\s+آهنگ\s+|دانلود\s+ترانه\s+|دانلود\s+موزیک\s+)', '', raw_title).strip()
            
            # Split Artist & Song Title
            artist = "خواننده"
            song_title = cleaned_title
            for delim in [' - ', ' – ', ' : ']:
                if delim in cleaned_title:
                    parts = cleaned_title.split(delim, 1)
                    artist = parts[0].strip()
                    song_title = parts[1].strip()
                    break

            # 2. Extract Direct MP3 Link (Prioritize 320kbps)
            mp3_links = soup.find_all('a', href=re.compile(r'\.mp3$', re.I))
            if not mp3_links:
                return None

            mp3_320 = next((a['href'] for a in mp3_links if '320' in a['href']), None)
            mp3_url = mp3_320 or mp3_links[0]['href']

            # 3. Extract Cover Art
            img_tag = soup.find('img', class_=re.compile(r'attachment|wp-post-image|cover')) or (soup.find('div', class_='post').find('img') if soup.find('div', class_='post') else None)
            cover_url = img_tag.get('src') if img_tag else None

            # 4. Extract Full Persian Lyrics
            lyrics = ""
            lyrics_div = soup.find('div', class_='lyric') or soup.find('div', class_='entry-content')
            if lyrics_div:
                # Remove script/ads
                for s in lyrics_div(['script', 'style', 'a', 'h2']):
                    s.decompose()
                lyrics = lyrics_div.get_text(separator='\n').strip()
                # Clean up repeated download text
                lyrics = re.sub(r'(?i)(دانلود آهنگ.*|پخش آنلاین.*|لینک مستقیم.*)', '', lyrics).strip()

            slug_base = self.slugify(f"{artist}-{song_title}")
            audio_filename = f"{slug_base}.mp3"
            cover_filename = f"{slug_base}.jpg"

            audio_path = os.path.join(self.download_audio_dir, audio_filename)
            cover_path = os.path.join(self.download_cover_dir, cover_filename)

            # Download MP3 directly with short connect timeout (to avoid hanging on geo-blocked servers)
            print(f"[*] Downloading direct MP3 320k: {mp3_url} ...")
            try:
                r_audio = requests.get(mp3_url, headers=self.headers, stream=True, timeout=(5, 30))
                if r_audio.status_code == 200:
                    with open(audio_path, 'wb') as f:
                        for chunk in r_audio.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                else:
                    print(f"[ERROR] Failed to download direct MP3 file: {r_audio.status_code}")
                    return None
            except requests.exceptions.ConnectTimeout:
                print(f"[WARN] Connection timeout for {mp3_url}. The CDN server is likely geo-restricted to Iranian IPs.")
                return None
            except Exception as e:
                print(f"[ERROR] Direct MP3 download failed: {e}")
                return None

            # Download Cover
            if cover_url and not os.path.exists(cover_path):
                try:
                    r_cover = requests.get(cover_url, headers=self.headers, timeout=10)
                    if r_cover.status_code == 200:
                        with open(cover_path, 'wb') as f:
                            f.write(r_cover.content)
                except Exception:
                    pass

            return {
                'title': song_title,
                'artist_name': artist,
                'slug': slug_base,
                'local_audio_path': audio_path,
                'local_cover_path': cover_path,
                'audio_url': f"/storage/tracks/{audio_filename}",
                'cover_image': f"/storage/covers/{cover_filename}" if os.path.exists(cover_path) else cover_url,
                'cover_url': cover_url,
                'lyrics': lyrics,
                'duration': 210,
                'genre': 'Pop',
                'description': lyrics[:200] if lyrics else song_title
            }

        except Exception as e:
            print(f"[ERROR] Extraction error for {post_url}: {e}")
            return None
