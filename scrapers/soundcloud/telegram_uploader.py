import os
import requests
from typing import Dict, Any, Optional

class TelegramUploader:
    """
    Handles uploading audio files and artwork directly to a Telegram Channel / Bot
    and retrieves streaming / download links without needing costly media servers.
    """
    def __init__(self, bot_token: Optional[str] = None, channel_id: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.channel_id = channel_id or os.getenv("TELEGRAM_CHANNEL_ID")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.channel_id)

    def upload_audio(self, file_path: str, title: str, performer: str, caption: str = "") -> Optional[Dict[str, Any]]:
        """
        Uploads an audio file (.mp3) to Telegram using sendAudio and gets file stream info.
        """
        if not self.is_configured():
            print("[WARN] Telegram Bot Token or Channel ID not configured.")
            return None

        if not os.path.exists(file_path):
            print(f"[ERROR] Audio file not found: {file_path}")
            return None

        url = f"{self.base_url}/sendAudio"
        
        with open(file_path, 'rb') as audio_file:
            files = {'audio': audio_file}
            data = {
                'chat_id': self.channel_id,
                'title': title,
                'performer': performer,
                'caption': caption or f"🎵 {title} - {performer}",
            }
            try:
                response = requests.post(url, data=data, files=files, timeout=60)
                res_data = response.json()
                if not res_data.get('ok'):
                    print(f"[ERROR] Telegram upload failed: {res_data.get('description')}")
                    return None

                audio_obj = res_data['result']['audio']
                file_id = audio_obj['file_id']
                file_unique_id = audio_obj['file_unique_id']
                message_id = res_data['result']['message_id']
                duration = audio_obj.get('duration', 0)

                # Get direct file path from Telegram API
                file_url = self.get_direct_file_url(file_id)

                return {
                    'file_id': file_id,
                    'file_unique_id': file_unique_id,
                    'message_id': message_id,
                    'duration': duration,
                    'file_url': file_url,
                    # Proxy stream link via website endpoint so bot token is not exposed in frontend
                    'stream_url': f"/api/stream?file_id={file_id}",
                    'direct_bot_url': file_url
                }
            except Exception as e:
                print(f"[ERROR] Telegram upload exception: {e}")
                return None

    def upload_photo(self, file_path: str, caption: str = "") -> Optional[str]:
        """
        Uploads cover photo to Telegram and retrieves the direct link / stream link.
        """
        if not self.is_configured() or not os.path.exists(file_path):
            return None

        url = f"{self.base_url}/sendPhoto"
        with open(file_path, 'rb') as photo_file:
            files = {'photo': photo_file}
            data = {
                'chat_id': self.channel_id,
                'caption': caption
            }
            try:
                response = requests.post(url, data=data, files=files, timeout=30)
                res_data = response.json()
                if res_data.get('ok'):
                    # Get highest resolution photo (last item in array)
                    photos = res_data['result']['photo']
                    best_photo = photos[-1]
                    file_id = best_photo['file_id']
                    return f"/api/stream?file_id={file_id}"
            except Exception as e:
                print(f"[WARN] Failed to upload photo to Telegram: {e}")

        return None

    def get_direct_file_url(self, file_id: str) -> Optional[str]:
        """
        Resolves file_id to a direct download/stream link on Telegram Bot API servers.
        """
        try:
            url = f"{self.base_url}/getFile?file_id={file_id}"
            resp = requests.get(url, timeout=15)
            data = resp.json()
            if data.get('ok'):
                file_path = data['result']['file_path']
                return f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
        except Exception as e:
            print(f"[ERROR] Getting direct file URL: {e}")
        return None
