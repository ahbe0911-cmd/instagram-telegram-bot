# ربات تلگرام دانلود پست و ریلز عمومی Instagram

یک ربات فارسی آمادهٔ اجرا که لینک پست، ریلز یا آلبوم چنداسلایدی عمومی Instagram را دریافت و رسانه‌ها را داخل Telegram ارسال می‌کند.

## امکانات

- دریافت عکس، ویدئو، ریلز و آلبوم چنداسلایدی عمومی
- ارسال آلبوم‌ها در گروه‌های حداکثر ۱۰تایی با حفظ ترتیب
- نمایش نام کاربری و کپشن پست
- پیام‌های کاملاً فارسی
- محدودسازی تعداد درخواست هر کاربر و دانلودهای هم‌زمان
- حذف خودکار فایل‌های موقت پس از ارسال
- مدیریت خطای محتوای خصوصی، لینک حذف‌شده، قطعی و محدودیت موقت Instagram
- Docker، فایل اجرای Worker و آزمون خودکار GitHub Actions

## محدودیت‌های واقعی

- فقط لینک‌های `p`، `reel`، `reels` و `tv` مربوط به محتوای عمومی پشتیبانی می‌شوند.
- استوری، صفحهٔ کاربری و محتوای خصوصی پشتیبانی نمی‌شود.
- این پروژه از API رسمی Instagram استفاده نمی‌کند؛ بنابراین تغییرات یا محدودیت‌های Instagram می‌تواند موقتاً دریافت را مختل کند.
- Bot API ابری Telegram برای آپلود مستقیم ویدئو/فایل سقف ۵۰ مگابایت دارد. مقدار پیش‌فرض پروژه ۴۹ مگابایت است.
- فقط محتوایی را ذخیره یا بازنشر کنید که مالک آن هستید یا اجازهٔ لازم را دارید.

## راه‌اندازی سریع

### ۱. ساخت ربات

1. در Telegram وارد `@BotFather` شوید.
2. دستور `/newbot` را بفرستید و نام و نام کاربری ربات را انتخاب کنید.
3. توکن ایجادشده را کپی کنید؛ آن را برای هیچ‌کس نفرستید و داخل GitHub قرار ندهید.

### ۲. اجرای مستقیم با Python 3.10 یا جدیدتر

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

در فایل `.env` مقدار `TELEGRAM_BOT_TOKEN` را با توکن واقعی جایگزین کنید، سپس:

```bash
PYTHONPATH=src python -m ig_telegram_bot
```

در Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
python -m ig_telegram_bot
```

### ۳. اجرا با Docker

```bash
cp .env.example .env
docker compose up -d --build
```

## استقرار ابری از طریق GitHub

1. فایل‌های پروژه را در یک مخزن خصوصی GitHub بارگذاری کنید.
2. در سرویس میزبانی‌ای که Docker یا Background Worker را پشتیبانی می‌کند، مخزن را متصل کنید.
3. نوع سرویس را `Worker` انتخاب کنید؛ برای Docker فرمان اضافی لازم نیست. در حالت Python فرمان اجرا این است:

```bash
python -m ig_telegram_bot
```

4. متغیر محرمانهٔ `TELEGRAM_BOT_TOKEN` را در تنظیمات میزبان ثبت کنید.
5. اگر نصب پروژه به‌صورت package انجام نمی‌شود، متغیر `PYTHONPATH=src` را نیز اضافه کنید.

این ربات از Long Polling استفاده می‌کند؛ بنابراین فقط یک نمونه از آن را هم‌زمان اجرا کنید.

## تنظیمات اختیاری

| متغیر | پیش‌فرض | توضیح |
| --- | ---: | --- |
| `MAX_CONCURRENT_DOWNLOADS` | `2` | تعداد دانلود هم‌زمان کل ربات |
| `MAX_REQUESTS_PER_MINUTE` | `4` | سقف درخواست هر کاربر در یک دقیقه |
| `MAX_UPLOAD_MB` | `49` | سقف ارسال ویدئو/فایل؛ حداکثر مجاز در این نسخه ۴۹ |
| `LOG_LEVEL` | `INFO` | سطح گزارش‌گیری |

## آزمون

```bash
pip install -r requirements.txt -r requirements-dev.txt
ruff check src tests
PYTHONPATH=src pytest
```

## امنیت

- فایل `.env` در `.gitignore` قرار دارد.
- توکن ربات را در پیام، تصویر، کد یا Commit منتشر نکنید.
- اگر توکن لو رفت، در BotFather آن را فوراً لغو و توکن جدید بسازید.
- پروژه هیچ رمز عبور Instagram دریافت یا ذخیره نمی‌کند.

## مبنای فنی

- [مستندات رسمی Instaloader به‌عنوان ماژول](https://instaloader.github.io/as-module.html)
- [مستندات رسمی python-telegram-bot](https://docs.python-telegram-bot.org/)
- [مستندات رسمی Telegram Bot API](https://core.telegram.org/bots/api)
