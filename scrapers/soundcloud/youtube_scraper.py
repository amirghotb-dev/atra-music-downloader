import re
import os
import unicodedata
import requests
import yt_dlp
from typing import Dict, Any, Optional, List

class YouTubeMusicScraper:
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
        """Parses clean title, artist name, and strips YouTube noise tags."""
        cleaned = re.sub(r'(?i)\b(official music video|official audio|music video|lyric video|audio|remix|hd|4k|320kbps|128kbps|album version|visualizer)\b', '', raw_title)
        cleaned = re.sub(r'[\[\]\(\)\{\}]', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -_|:')

        uploader_clean = re.sub(r'(?i)(\s*-\s*topic|\s*official|\s*channel|\s*music)', '', uploader).strip()
        artist = uploader_clean or uploader
        title = cleaned

        for delimiter in [' - ', ' : ', ' | ']:
            if delimiter in cleaned:
                parts = [p.strip() for p in cleaned.split(delimiter, 1)]
                if len(parts) == 2 and parts[0] and parts[1]:
                    artist = parts[0]
                    title = parts[1]
                    break

        return {
            "title": title.strip() or raw_title,
            "artist": artist.strip() or uploader_clean
        }

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Searches YouTube Music / YouTube with yt-dlp."""
        search_query = f"ytsearch{limit}:{query} audio"
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'skip_download': True,
            'ignoreerrors': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            results = []
            if info and 'entries' in info:
                for entry in info['entries']:
                    if not entry:
                        continue
                    results.append({
                        'id': entry.get('id'),
                        'url': entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                        'title': entry.get('title'),
                        'uploader': entry.get('uploader') or entry.get('channel'),
                        'duration': entry.get('duration') or 0,
                    })
            return results

    def get_tracks(self, url_or_query: str, limit: int = 20) -> List[str]:
        """
        Extracts track URLs from a YouTube channel/artist (both Songs and Music Videos),
        playlists, releases or search queries.
        """
        urls = []
        is_url = url_or_query.startswith("http://") or url_or_query.startswith("https://")

        if is_url:
            target_url = url_or_query
            if "music.youtube.com" in target_url:
                target_url = target_url.replace("music.youtube.com", "www.youtube.com")

            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'skip_download': True,
                'ignoreerrors': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'
            }

            # If user provided a Channel root like /@chavoshiofficial
            # Extract both from /videos (Music Videos) and /releases (Official Songs & Albums)
            targets_to_scan = []
            if "/@" in target_url and not any(sub in target_url for sub in ["/videos", "/releases", "/playlists"]):
                targets_to_scan.append(f"{target_url.rstrip('/')}/videos")
                targets_to_scan.append(f"{target_url.rstrip('/')}/releases")
            else:
                targets_to_scan.append(target_url)

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    for scan_url in targets_to_scan:
                        if len(urls) >= limit:
                            break
                        info = ydl.extract_info(scan_url, download=False)
                        if info and 'entries' in info:
                            for entry in info['entries']:
                                if not entry:
                                    continue
                                
                                entry_url = entry.get('url') or (f"https://www.youtube.com/watch?v={entry.get('id')}" if entry.get('id') else None)
                                
                                # If entry is a release/album/playlist, extract sub-tracks
                                if entry.get('_type') == 'playlist' or (entry_url and 'playlist' in entry_url):
                                    try:
                                        sub_info = ydl.extract_info(entry_url, download=False)
                                        if sub_info and 'entries' in sub_info:
                                            for sub_entry in sub_info['entries']:
                                                sub_u = sub_entry.get('url') or (f"https://www.youtube.com/watch?v={sub_entry.get('id')}" if sub_entry.get('id') else None)
                                                if sub_u and sub_u not in urls:
                                                    urls.append(sub_u)
                                                if len(urls) >= limit:
                                                    break
                                    except Exception:
                                        pass
                                elif entry_url and entry_url not in urls:
                                    urls.append(entry_url)

                                if len(urls) >= limit:
                                    break
            except Exception as e:
                print(f"[WARN] Error extracting YouTube Music URLs: {e}")

        # Fallback to search query
        if not urls:
            results = self.search(url_or_query, limit=limit)
            urls = [r['url'] for r in results if r.get('url')]

        return urls[:limit]

    def extract_track_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Extracts audio metadata and max-res cover art from YouTube."""
        cookies_file = os.getenv("YOUTUBE_COOKIES_FILE", "cookies.txt")
        cookies_content = os.getenv("YOUTUBE_COOKIES")

        if cookies_content and not os.path.exists("cookies.txt"):
            with open("cookies.txt", "w", encoding="utf-8") as f:
                f.write(cookies_content)
            cookies_file = "cookies.txt"

        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'ignoreerrors': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['mweb', 'web_embedded', 'android', 'ios']
                }
            },
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'
        }

        if os.path.exists(cookies_file):
            ydl_opts['cookiefile'] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None

                raw_title = info.get('title', '')
                uploader = info.get('uploader') or info.get('channel') or info.get('artist') or 'Unknown Artist'
                parsed = self.clean_title_and_artist(raw_title, uploader)

                # Highest quality thumbnail
                thumbnail = info.get('thumbnail')
                if 'thumbnails' in info and info['thumbnails']:
                    thumbnails = sorted(info['thumbnails'], key=lambda x: x.get('width', 0) or 0, reverse=True)
                    if thumbnails:
                        thumbnail = thumbnails[0].get('url')

                duration = int(info.get('duration') or 0)
                likes = int(info.get('like_count') or 0)
                views = int(info.get('view_count') or 0)
                genre = info.get('genre') or 'Persian Pop'
                description = info.get('description', '')

                source_id = str(info.get('id'))
                webpage_url = info.get('webpage_url') or f"https://www.youtube.com/watch?v={source_id}"

                return {
                    'source_id': source_id,
                    'url': webpage_url,
                    'video_url': webpage_url,
                    'title': parsed['title'],
                    'raw_title': raw_title,
                    'artist_name': parsed['artist'],
                    'uploader': uploader,
                    'duration': duration,
                    'cover_url': thumbnail,
                    'stream_count': views,
                    'likes_count': likes,
                    'genre': genre,
                    'description': description,
                    'lyrics': description if ('متن' in description or 'ترانه' in description or 'lyrics' in description.lower()) else ''
                }
            except Exception as e:
                print(f"[ERROR] Extracting info for {url}: {e}")
                return None

    def download_track(self, url: str, filename_prefix: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Downloads audio as 320k MP3 and retrieves cover art."""
        info = self.extract_track_info(url)
        if not info:
            return None

        actual_url = info.get('url') or url
        slug_base = filename_prefix or self.slugify(f"{info['artist_name']}-{info['title']}")
        audio_filename = f"{slug_base}.mp3"
        cover_filename = f"{slug_base}.jpg"

        audio_path = os.path.join(self.download_audio_dir, audio_filename)
        cover_path = os.path.join(self.download_cover_dir, cover_filename)

        # 1. Download Cover Artwork
        if info.get('cover_url') and not os.path.exists(cover_path):
            try:
                resp = requests.get(info['cover_url'], timeout=15)
                if resp.status_code == 200:
                    with open(cover_path, 'wb') as f:
                        f.write(resp.content)
            except Exception as e:
                print(f"[WARN] Failed to download cover: {e}")

        # 2. Download MP3 Audio
        cookies_file = os.getenv("YOUTUBE_COOKIES_FILE", "cookies.txt")
        cookies_content = os.getenv("YOUTUBE_COOKIES")

        if cookies_content and not os.path.exists("cookies.txt"):
            with open("cookies.txt", "w", encoding="utf-8") as f:
                f.write(cookies_content)
            cookies_file = "cookies.txt"

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.download_audio_dir, f"{slug_base}.%(ext)s"),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
            'quiet': False,
            'no_warnings': False,
            'ignoreerrors': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['mweb', 'web_embedded', 'android', 'ios']
                }
            },
            'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'
        }

        if os.path.exists(cookies_file):
            ydl_opts['cookiefile'] = cookies_file

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([actual_url])
        except Exception as e:
            print(f"[ERROR] Downloading YouTube audio {actual_url}: {e}")
            return None

        if not os.path.exists(audio_path):
            print(f"[ERROR] Audio file not found at {audio_path}")
            return None

        info['local_audio_path'] = audio_path
        info['local_cover_path'] = cover_path
        info['audio_url'] = f"/storage/tracks/{audio_filename}"
        info['cover_image'] = f"/storage/covers/{cover_filename}" if os.path.exists(cover_path) else info.get('cover_url')
        info['slug'] = slug_base

        return info
