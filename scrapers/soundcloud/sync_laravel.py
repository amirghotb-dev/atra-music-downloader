import sqlite3
import os
import json
import time
from typing import Dict, Any, Optional

class LaravelDbSyncer:
    def __init__(self, db_path: str = "database/database.sqlite"):
        self.db_path = db_path

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def find_or_create_artist(self, name: str, avatar_url: Optional[str] = None) -> int:
        """Find existing artist or create a new one."""
        conn = self.get_connection()
        cursor = conn.cursor()
        now = time.strftime('%Y-%m-%d %H:%M:%S')

        # Check existing by name
        cursor.execute("SELECT id FROM artists WHERE name = ? OR slug = ?", (name, name.strip().lower().replace(' ', '-')))
        row = cursor.fetchone()
        if row:
            conn.close()
            return row[0]

        # Generate slug
        slug = name.strip().lower().replace(' ', '-')
        # Ensure uniqueness
        cursor.execute("SELECT id FROM artists WHERE slug = ?", (slug,))
        if cursor.fetchone():
            slug = f"{slug}-{int(time.time())}"

        cursor.execute("""
            INSERT INTO artists (name, slug, image_url, created_at)
            VALUES (?, ?, ?, ?)
        """, (name, slug, avatar_url, now))
        artist_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return artist_id

    def find_or_create_genre(self, name: str) -> Optional[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        now = time.strftime('%Y-%m-%d %H:%M:%S')

        # Map typical genres
        genre_name = 'پاپ'
        genre_slug = 'pop'
        name_lower = name.lower()
        if 'rap' in name_lower or 'hip' in name_lower or 'trap' in name_lower:
            genre_name = 'رپ و هیپ‌هاپ'
            genre_slug = 'rap'
        elif 'electronic' in name_lower or 'chill' in name_lower or 'dance' in name_lower:
            genre_name = 'الکترونیک'
            genre_slug = 'electronic'
        elif 'traditional' in name_lower or 'sonati' in name_lower:
            genre_name = 'سنتی'
            genre_slug = 'traditional'
        elif 'rock' in name_lower:
            genre_name = 'راک'
            genre_slug = 'rock'

        cursor.execute("SELECT id FROM genres WHERE slug = ?", (genre_slug,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return row[0]

        cursor.execute("""
            INSERT INTO genres (name, slug, created_at)
            VALUES (?, ?, ?)
        """, (genre_name, genre_slug, now))
        genre_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return genre_id

    def sync_track(self, track_info: Dict[str, Any]) -> Optional[int]:
        """Saves or updates track in SQLite database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        now = time.strftime('%Y-%m-%d %H:%M:%S')

        title = track_info['title']
        artist_name = track_info['artist_name']
        cover_image = track_info.get('cover_image')
        audio_url = track_info.get('audio_url')
        duration = track_info.get('duration', 0)
        stream_count = track_info.get('stream_count', 0)
        likes_count = track_info.get('likes_count', 0)
        genre_str = track_info.get('genre', 'Pop')

        artist_id = self.find_or_create_artist(artist_name, cover_image)
        genre_id = self.find_or_create_genre(genre_str)

        slug = track_info.get('slug') or f"{artist_name}-{title}".strip().lower().replace(' ', '-')

        # Check if track already exists
        cursor.execute("SELECT id FROM tracks WHERE slug = ? OR (title = ? AND artist_id = ?)", (slug, title, artist_id))
        row = cursor.fetchone()

        if row:
            track_id = row[0]
            cursor.execute("""
                UPDATE tracks SET
                    audio_url = ?,
                    cover_image = ?,
                    duration = ?,
                    plays_count = ?,
                    likes_count = ?
                WHERE id = ?
            """, (audio_url, cover_image, duration, stream_count, likes_count, track_id))
            print(f"[UPDATED] Track: {title} by {artist_name} (ID: {track_id})")
        else:
            cursor.execute("""
                INSERT INTO tracks (
                    artist_id, album_id, genre_id, title, slug,
                    audio_url, cover_image, duration, plays_count, likes_count,
                    is_featured, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                artist_id, None, genre_id, title, slug,
                audio_url, cover_image, duration, stream_count, likes_count,
                1, now
            ))
            track_id = cursor.lastrowid
            print(f"[INSERTED] Track: {title} by {artist_name} (ID: {track_id})")

        conn.commit()
        conn.close()
        return track_id
