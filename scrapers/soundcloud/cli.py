import argparse
import sys
import os
from downloader import SoundCloudScraper
from sync_laravel import LaravelDbSyncer
from telegram_uploader import TelegramUploader
from api_syncer import AtraApiSyncer

def main():
    parser = argparse.ArgumentParser(description="SoundCloud Persian Music Scraper with Telegram Storage & Website API Sync")
    parser.add_argument("action", choices=["search", "download", "sync", "discover", "telegram-sync"], help="Action to perform")
    parser.add_argument("target", nargs="?", default="", help="Query or URL")
    parser.add_argument("--limit", type=int, default=5, help="Number of items to fetch/download")
    parser.add_argument("--db", default=".data/music.db", help="Path to SQLite database")
    parser.add_argument("--telegram-token", default=os.getenv("TELEGRAM_BOT_TOKEN"), help="Telegram Bot Token")
    parser.add_argument("--telegram-chat", default=os.getenv("TELEGRAM_CHANNEL_ID"), help="Telegram Channel/Chat ID")
    parser.add_argument("--api-url", default=os.getenv("SITE_API_URL", "http://localhost:4321"), help="Atra Music API URL")
    parser.add_argument("--api-secret", default=os.getenv("INGEST_SECRET", "atra-secret-key-2026"), help="Atra Music Ingest API Secret")

    args = parser.parse_args()

    scraper = SoundCloudScraper(
        download_audio_dir="public/storage/tracks",
        download_cover_dir="public/storage/covers"
    )
    syncer = LaravelDbSyncer(db_path=args.db)
    tg_uploader = TelegramUploader(bot_token=args.telegram_token, channel_id=args.telegram_chat)
    api_syncer = AtraApiSyncer(api_base_url=args.api_url, api_secret=args.api_secret)

    if args.action == "search":
        query = args.target or "persian music 2026"
        print(f"[*] Searching SoundCloud for: '{query}' (limit: {args.limit})...\n")
        results = scraper.search(query, limit=args.limit)
        for i, item in enumerate(results, 1):
            print(f"{i}. [{item['id']}] {item['title']}")
            print(f"   Uploader: {item['uploader']} | Duration: {item['duration']}s")
            print(f"   URL: {item['url']}\n")

    elif args.action in ["download", "sync", "telegram-sync"]:
        target = args.target
        if not target:
            print("[ERROR] Please provide a SoundCloud URL or search query.")
            sys.exit(1)

        print(f"[*] Fetching batch of up to {args.limit} tracks for: '{target}'...")
        urls = scraper.get_artist_or_playlist_tracks(target, limit=args.limit)

        print(f"[*] Found {len(urls)} tracks to process.\n")
        for idx, url in enumerate(urls, 1):
            print(f"[{idx}/{len(urls)}] Processing: {url}")
            track_info = scraper.download_track(url)
            if not track_info:
                print(f"[X] Failed to download {url}\n")
                continue

            # If telegram-sync is selected, upload media to Telegram for free zero-cost hosting
            if args.action == "telegram-sync" or tg_uploader.is_configured():
                print(f"[*] Uploading audio to Telegram Channel ({args.telegram_chat})...")
                tg_audio = tg_uploader.upload_audio(
                    file_path=track_info['local_audio_path'],
                    title=track_info['title'],
                    performer=track_info['artist_name']
                )

                if tg_audio:
                    print(f"[✓] Audio uploaded to Telegram! file_id: {tg_audio['file_id']}")
                    # Use telegram stream link or direct bot url
                    track_info['audio_url'] = tg_audio.get('stream_url') or tg_audio.get('file_url')
                    
                    # Optionally upload cover photo to Telegram too
                    if os.path.exists(track_info.get('local_cover_path', '')):
                        tg_cover = tg_uploader.upload_photo(track_info['local_cover_path'], caption=track_info['title'])
                        if tg_cover:
                            track_info['cover_image'] = tg_cover
                else:
                    print("[WARN] Telegram upload failed, keeping local URL fallback.")

            # Sync via Website API
            print(f"[*] Syncing metadata to Atra Music Website ({args.api_url})...")
            api_syncer.send_track(track_info)

            # Also sync locally if DB exists
            if os.path.exists(os.path.dirname(args.db) or "."):
                try:
                    syncer.sync_track(track_info)
                except Exception as e:
                    pass

            # Cleanup local disk storage after uploading to Telegram (0 server disk space used!)
            if args.action == "telegram-sync":
                try:
                    if os.path.exists(track_info.get('local_audio_path', '')):
                        os.remove(track_info['local_audio_path'])
                    if os.path.exists(track_info.get('local_cover_path', '')):
                        os.remove(track_info['local_cover_path'])
                    print("[✓] Local temp files cleaned up to save server storage space.")
                except Exception as e:
                    print(f"[WARN] Error cleaning temp files: {e}")

            print(f"[✓] Successfully finished: {track_info['artist_name']} - {track_info['title']}")
            print(f"    Stream URL: {track_info['audio_url']}\n")

    elif args.action == "discover":
        categories = [
            "persian rap 2026",
            "shadmehr aghili",
            "shervin hajipour",
            "homayoun shajarian",
            "persian pop remix"
        ]
        print(f"[*] Starting Auto-Discovery across {len(categories)} Persian music genres...\n")
        for cat in categories:
            print(f"\n=== Fetching category: {cat} ===")
            results = scraper.search(cat, limit=2)
            for res in results:
                if res.get('url'):
                    print(f"[-] Processing: {res['title']}")
                    track_info = scraper.download_track(res['url'])
                    if track_info:
                        if tg_uploader.is_configured():
                            tg_audio = tg_uploader.upload_audio(
                                file_path=track_info['local_audio_path'],
                                title=track_info['title'],
                                performer=track_info['artist_name']
                            )
                            if tg_audio:
                                track_info['audio_url'] = tg_audio.get('stream_url') or tg_audio.get('file_url')
                        api_syncer.send_track(track_info)

    print("\n[✔] All done!")

if __name__ == "__main__":
    main()
