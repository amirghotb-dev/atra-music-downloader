import argparse
import sys
import os
from downloader import SoundCloudScraper
from youtube_scraper import YouTubeMusicScraper
from direct_scraper import PersianMusicDirectScraper
from sync_laravel import LaravelDbSyncer
from telegram_uploader import TelegramUploader
from api_syncer import AtraApiSyncer

def process_track(track_info, args, tg_uploader, api_syncer):
    """Unified handler for uploading audio to Telegram and syncing to website API."""
    if not track_info:
        return False

    if args.action == "telegram-sync" or tg_uploader.is_configured():
        print(f"[*] Uploading audio to Telegram Channel ({args.telegram_chat})...")
        tg_audio = tg_uploader.upload_audio(
            file_path=track_info['local_audio_path'],
            title=track_info['title'],
            performer=track_info['artist_name']
        )
        if tg_audio:
            print(f"[✓] Audio uploaded to Telegram! file_id: {tg_audio['file_id']}")
            track_info['audio_url'] = tg_audio.get('stream_url') or tg_audio.get('file_url')
        else:
            print("[WARN] Telegram upload failed, keeping local URL fallback.")

    print(f"[*] Syncing metadata & lyrics to Atra Music Website ({args.api_url})...")
    api_syncer.send_track(track_info)

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
    return True

def main():
    parser = argparse.ArgumentParser(description="Multi-Source Persian Music Scraper (SoundCloud / YouTube / Direct CDN) with Telegram Storage & Website API Sync")
    parser.add_argument("action", choices=["search", "download", "sync", "discover", "telegram-sync"], help="Action to perform")
    parser.add_argument("target", nargs="?", default="", help="Artist name, Search Query, or YouTube/SoundCloud URL")
    parser.add_argument("--source", choices=["auto", "soundcloud", "youtube", "direct"], default="auto", help="Platform source")
    parser.add_argument("--limit", type=int, default=5, help="Number of items to fetch/download")
    parser.add_argument("--db", default=".data/music.db", help="Path to SQLite database")
    parser.add_argument("--telegram-token", default=os.getenv("TELEGRAM_BOT_TOKEN"), help="Telegram Bot Token")
    parser.add_argument("--telegram-chat", default=os.getenv("TELEGRAM_CHANNEL_ID"), help="Telegram Channel/Chat ID")
    parser.add_argument("--api-url", default=os.getenv("SITE_API_URL", "http://localhost:4321"), help="Atra Music API URL")
    parser.add_argument("--api-secret", default=os.getenv("INGEST_SECRET", "atra-secret-key-2026"), help="Atra Music Ingest API Secret")

    args = parser.parse_args()

    tg_uploader = TelegramUploader(bot_token=args.telegram_token, channel_id=args.telegram_chat)
    api_syncer = AtraApiSyncer(api_base_url=args.api_url, api_secret=args.api_secret)

    # Detect platform routing
    target = args.target.strip()
    is_url = target.startswith("http://") or target.startswith("https://")

    if args.source == "direct" or ("music-fa.com" in target or "musics-fa.com" in target):
        active_source = "direct"
    elif args.source == "youtube" or ("youtube.com" in target or "youtu.be" in target):
        active_source = "youtube"
    elif args.source == "soundcloud" or ("soundcloud.com" in target):
        active_source = "soundcloud"
    else:  # auto
        if "youtube.com" in target or "youtu.be" in target:
            active_source = "youtube"
        elif "soundcloud.com" in target:
            active_source = "soundcloud"
        elif "music-fa.com" in target or "musics-fa.com" in target:
            active_source = "direct"
        else:
            # Query / Artist name in auto mode:
            # Default to SoundCloud for 100% global reliability without geo-blocking
            active_source = "soundcloud"

    if args.action == "search":
        query = target or "persian music 2026"
        print(f"[*] Searching ({active_source}) for: '{query}' (limit: {args.limit})...\n")
        if active_source == "youtube":
            scraper = YouTubeMusicScraper()
            results = scraper.search(query, limit=args.limit)
        else:
            scraper = SoundCloudScraper()
            results = scraper.search(query, limit=args.limit)

        for i, item in enumerate(results, 1):
            print(f"{i}. [{item.get('id')}] {item.get('title')}")
            print(f"   Uploader: {item.get('uploader')} | Duration: {item.get('duration')}s")
            print(f"   URL: {item.get('url')}\n")

    elif args.action in ["download", "sync", "telegram-sync"]:
        if not target:
            print("[ERROR] Please provide a URL or search query.")
            sys.exit(1)

        print(f"[*] Source: [{active_source.upper()}] | Fetching batch of up to {args.limit} tracks for: '{target}'...")

        success_count = 0

        # --- SOURCE: SOUNDCLOUD ---
        if active_source == "soundcloud":
            sc_scraper = SoundCloudScraper()
            urls = sc_scraper.get_artist_or_playlist_tracks(target, limit=args.limit)
            print(f"[*] Found {len(urls)} tracks on SoundCloud.\n")
            for idx, url in enumerate(urls, 1):
                print(f"[{idx}/{len(urls)}] Processing SoundCloud track: {url}")
                track_info = sc_scraper.download_track(url)
                if track_info and process_track(track_info, args, tg_uploader, api_syncer):
                    success_count += 1
                else:
                    print(f"[X] Failed to process {url}\n")

        # --- SOURCE: YOUTUBE MUSIC ---
        elif active_source == "youtube":
            yt_scraper = YouTubeMusicScraper()
            urls = yt_scraper.get_tracks(target, limit=args.limit)
            print(f"[*] Found {len(urls)} tracks on YouTube Music.\n")
            for idx, url in enumerate(urls, 1):
                print(f"[{idx}/{len(urls)}] Processing YouTube track: {url}")
                track_info = yt_scraper.download_track(url)
                if track_info and process_track(track_info, args, tg_uploader, api_syncer):
                    success_count += 1
                else:
                    print(f"[X] Failed to process {url}\n")

        # --- SOURCE: DIRECT PERSIAN CDN (with automatic SoundCloud fallback) ---
        elif active_source == "direct":
            direct_scraper = PersianMusicDirectScraper()
            post_urls = direct_scraper.search_tracks(target, limit=args.limit) if not is_url else [target]
            print(f"[*] Found {len(post_urls)} tracks on Direct Persian Music CDN.\n")
            for idx, p_url in enumerate(post_urls, 1):
                print(f"[{idx}/{len(post_urls)}] Processing Direct track: {p_url}")
                track_info = direct_scraper.extract_and_download(p_url)
                if track_info and process_track(track_info, args, tg_uploader, api_syncer):
                    success_count += 1
                else:
                    print(f"[X] Direct download failed for {p_url}\n")

            # Fallback if Direct CDN is geo-blocked or failed
            if success_count == 0 and not is_url:
                print("[WARN] Direct Iranian CDN is unreachable or geo-blocked for current IP.")
                print("[*] Automatically switching to SoundCloud fallback engine...\n")
                sc_scraper = SoundCloudScraper()
                sc_urls = sc_scraper.get_artist_or_playlist_tracks(target, limit=args.limit)
                for idx, sc_url in enumerate(sc_urls, 1):
                    print(f"[{idx}/{len(sc_urls)}] Processing SoundCloud fallback: {sc_url}")
                    track_info = sc_scraper.download_track(sc_url)
                    if track_info and process_track(track_info, args, tg_uploader, api_syncer):
                        success_count += 1
                    else:
                        print(f"[X] Failed to process {sc_url}\n")

        print(f"\n[✔] Batch finished! Successfully processed: {success_count} tracks.")

    elif args.action == "discover":
        categories = [
            "persian rap 2026",
            "shadmehr aghili",
            "shervin hajipour",
            "homayoun shajarian",
            "persian pop remix"
        ]
        print(f"[*] Starting Auto-Discovery across {len(categories)} Persian music genres...\n")
        sc_scraper = SoundCloudScraper()
        for cat in categories:
            print(f"\n=== Fetching category: {cat} ===")
            results = sc_scraper.search(cat, limit=2)
            for res in results:
                if res.get('url'):
                    print(f"[-] Processing: {res['title']}")
                    track_info = sc_scraper.download_track(res['url'])
                    if track_info:
                        process_track(track_info, args, tg_uploader, api_syncer)

    print("\n[✔] All done!")

if __name__ == "__main__":
    main()
