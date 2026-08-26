import re
import os
import unicodedata
import requests
import yt_dlp
from typing import Dict, Any, Optional, List

class SoundCloudScraper:
    def __init__(self, download_audio_dir: str = "public/storage/tracks", download_cover_dir: str = "public/storage/covers"):
        self.download_audio_dir = download_audio_dir
        self.download_cover_dir = download_cover_dir
        os.makedirs(self.download_audio_dir, exist_ok=True)
        os.makedirs(self.download_cover_dir, exist_ok=True)

    @staticmethod
    def slugify(text: str) -> str:
        """Create a URL friendly slug supporting Persian and English characters."""
        text = unicodedata.normalize('NFKC', text)
        text = re.sub(r'[^\w\s\u0600-\u06FF-]', '', text).strip()
        text = re.sub(r'[-\s]+', '-', text)
        return text.lower() or "track"

    @staticmethod
    def clean_title_and_artist(raw_title: str, uploader: str) -> Dict[str, str]:
        """
        Parses title and artist name intelligently.
        Handles cases like: 'Shadmehr Aghili - Taghdir [Remix]' or 'Ali Yasini | Jang'
        """
        # Remove noisy suffixes
        cleaned = re.sub(r'(?i)\b(320|128|kbps|remix|official audio|full album|podcast|music video|lyric video|prod\s*by.*)\b', '', raw_title)
        cleaned = re.sub(r'[\[\]\(\)\{\}]', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -_|:')

        artist = uploader
        title = cleaned

        # Check delimiters like " - ", " : ", " | "
        for delimiter in [' - ', ' : ', ' | ']:
            if delimiter in cleaned:
                parts = [p.strip() for p in cleaned.split(delimiter, 1)]
                if len(parts) == 2 and parts[0] and parts[1]:
                    # Usually artist is first, or title is first
                    # If uploader is in part[0], then part[0]=artist, part[1]=title
                    artist = parts[0]
                    title = parts[1]
                    break

        return {
            "title": title.strip() or raw_title,
            "artist": artist.strip() or uploader
        }

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search SoundCloud tracks by query using yt-dlp extractor."""
        search_query = f"scsearch{limit}:{query}"
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            results = []
            if 'entries' in info:
                for entry in info['entries']:
                    if not entry:
                        continue
                    results.append({
                        'id': entry.get('id'),
                        'url': entry.get('url'),
                        'title': entry.get('title'),
                        'uploader': entry.get('uploader'),
                        'uploader_url': entry.get('uploader_url'),
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail'),
                        'view_count': entry.get('view_count', 0),
                    })
            return results

    def extract_track_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Extracts complete track details and HD artwork from SoundCloud URL."""
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None

                raw_title = info.get('title', '')
                uploader = info.get('uploader') or info.get('artist') or 'Unknown Artist'
                parsed = self.clean_title_and_artist(raw_title, uploader)

                # Get High Definition artwork
                thumbnail = info.get('thumbnail')
                if thumbnail:
                    # Upgrade SoundCloud artwork to 500x500
                    thumbnail = re.sub(r'-(large|t\d+x\d+|badge)\.', '-t500x500.', thumbnail)

                duration = int(info.get('duration') or 0)
                likes = int(info.get('like_count') or 0)
                views = int(info.get('view_count') or 0)
                genre = info.get('genre') or 'Persian'

                return {
                    'source_id': str(info.get('id')),
                    'url': info.get('webpage_url') or url,
                    'title': parsed['title'],
                    'raw_title': raw_title,
                    'artist_name': parsed['artist'],
                    'uploader': uploader,
                    'uploader_id': info.get('uploader_id'),
                    'duration': duration,
                    'cover_url': thumbnail,
                    'stream_count': views,
                    'likes_count': likes,
                    'genre': genre,
                    'description': info.get('description', ''),
                }
            except Exception as e:
                print(f"[ERROR] Extracting info for {url}: {e}")
                return None

    def download_track(self, url: str, filename_prefix: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Downloads the audio file as MP3 (320k) and retrieves high-res cover."""
        info = self.extract_track_info(url)
        if not info:
            return None

        slug_base = filename_prefix or self.slugify(f"{info['artist_name']}-{info['title']}")
        audio_filename = f"{slug_base}.mp3"
        cover_filename = f"{slug_base}.jpg"

        audio_path = os.path.join(self.download_audio_dir, audio_filename)
        cover_path = os.path.join(self.download_cover_dir, cover_filename)

        # 1. Download Cover Image
        if info.get('cover_url') and not os.path.exists(cover_path):
            try:
                resp = requests.get(info['cover_url'], timeout=15)
                if resp.status_code == 200:
                    with open(cover_path, 'wb') as f:
                        f.write(resp.content)
            except Exception as e:
                print(f"[WARN] Failed to download cover: {e}")

        # 2. Download MP3 Audio
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.download_audio_dir, f"{slug_base}.%(ext)s"),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print(f"[ERROR] Downloading audio {url}: {e}")
            return None

        info['local_audio_path'] = audio_path
        info['local_cover_path'] = cover_path
        info['audio_url'] = f"/storage/tracks/{audio_filename}"
        info['cover_image'] = f"/storage/covers/{cover_filename}" if os.path.exists(cover_path) else info.get('cover_url')
        info['slug'] = slug_base

        return info
