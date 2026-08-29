# استقرار ربات

این پروژه با Long Polling اجرا می‌شود و به یک سرویس Worker یا Container همیشه‌روشن نیاز دارد.

## متغیر اجباری

- `TELEGRAM_BOT_TOKEN`: توکن BotFather. این مقدار را فقط در Secret/Environment میزبان وارد کنید و هرگز داخل Repository Commit نکنید.

## فرمان اجرا

```bash
python -m ig_telegram_bot
```

در استقرار بدون نصب Package، `PYTHONPATH=src` را نیز تنظیم کنید.

## Docker

Dockerfile در ریشه پروژه آماده است و CMD پیش‌فرض ربات را اجرا می‌کند.
