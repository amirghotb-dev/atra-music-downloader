import requests
import json
from typing import Dict, Any, Optional

class AtraApiSyncer:
    """
    Sends scraped & Telegram-uploaded track metadata directly to Atra Music API endpoint.
    """
    def __init__(self, api_base_url: str = "http://localhost:4321", api_secret: Optional[str] = None):
        self.api_base_url = api_base_url.rstrip("/")
        self.api_secret = api_secret or "atra-secret-key-2026"

    def send_track(self, track_data: Dict[str, Any]) -> bool:
        endpoint = f"{self.api_base_url}/api/ingest/track"
        headers = {
            "Content-Type": "application/json",
            "x-api-secret": self.api_secret
        }

        payload = {
            "title": track_data.get("title"),
            "artist_name": track_data.get("artist_name"),
            "slug": track_data.get("slug"),
            "audio_url": track_data.get("audio_url"),
            "video_url": track_data.get("video_url"),
            "cover_image": track_data.get("cover_image"),
            "duration": track_data.get("duration", 0),
            "stream_count": track_data.get("stream_count", 0),
            "likes_count": track_data.get("likes_count", 0),
            "genre": track_data.get("genre", "Pop"),
            "lyrics": track_data.get("lyrics", ""),
            "description": track_data.get("description", "")
        }

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=20)
            if resp.status_code in [200, 201]:
                res_json = resp.json()
                print(f"[API SYNC SUCCESS] Track ID: {res_json.get('track_id')} ({payload['title']})")
                return True
            else:
                print(f"[API SYNC ERROR {resp.status_code}]: {resp.text}")
                return False
        except Exception as e:
            print(f"[API SYNC EXCEPTION]: {e}")
            return False
