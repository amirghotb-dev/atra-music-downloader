# GitHub Scripts & Scraper Bundle

این پوشه شامل کلیه اسکریپت‌ها و گردش‌کارهای مورد نیاز برای اجرای خودکار در مخزن GitHub است.

## 📂 ساختار فایل‌ها:
- `.github/workflows/scraper.yml`: اکشن اجرای خودکار اسکرپر، آپلود به تلگرام و ارسال متادیتا به API سایت
- `scrapers/soundcloud/cli.py`: رابط خط فرمان اسکرپر
- `scrapers/soundcloud/downloader.py`: دانلودر صوت و کاور از ساندکلود با yt-dlp
- `scrapers/soundcloud/telegram_uploader.py`: ارسال صوت و کاور به ربات/کانال تلگرام
- `scrapers/soundcloud/api_syncer.py`: ارسال مشخصات به اندپوینت `/api/ingest/track` سایت
- `scrapers/soundcloud/sync_laravel.py`: همگام‌ساز دیتابیس لوکال SQLite

## 🔑 متغیرهای مورد نیاز در GitHub Repository Secrets:
1. `TELEGRAM_BOT_TOKEN`
2. `TELEGRAM_CHANNEL_ID`
3. `SITE_API_URL` (مثال: `https://your-domain.pages.dev`)
4. `INGEST_SECRET` (پیش‌فرض: `atra-secret-key-2026`)
