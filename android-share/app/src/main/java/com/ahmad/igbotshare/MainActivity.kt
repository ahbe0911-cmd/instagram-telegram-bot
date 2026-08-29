package com.ahmad.igbotshare

import android.app.Activity
import android.content.Intent
import android.graphics.Typeface
import android.net.Uri
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.Space
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(sourceIntent: Intent) {
        if (sourceIntent.action == Intent.ACTION_SEND) {
            val sharedText = sourceIntent.getStringExtra(Intent.EXTRA_TEXT)?.trim().orEmpty()
            val instagramUrl = extractInstagramUrl(sharedText)
            val textToSend = instagramUrl.ifBlank { sharedText }

            if (textToSend.isNotBlank()) {
                openTelegramBot(textToSend)
                finish()
                return
            }
        }

        showHome()
    }

    private fun showHome() {
        val padding = dp(24)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(padding, dp(44), padding, padding)
            layoutDirection = android.view.View.LAYOUT_DIRECTION_RTL
        }

        val title = TextView(this).apply {
            text = "دانلود با ربات"
            textSize = 28f
            setTypeface(typeface, Typeface.BOLD)
            gravity = Gravity.CENTER
        }
        root.addView(title, matchWrap())

        val bot = TextView(this).apply {
            text = "@$BOT_USERNAME"
            textSize = 18f
            gravity = Gravity.CENTER
            setPadding(0, dp(10), 0, 0)
        }
        root.addView(bot, matchWrap())

        val description = TextView(this).apply {
            text = "در Instagram روی Share بزن و «دانلود با ربات» را انتخاب کن. لینک مستقیماً در همین ربات تلگرام آماده می‌شود."
            textSize = 16f
            gravity = Gravity.CENTER
            setPadding(0, dp(24), 0, dp(20))
        }
        root.addView(description, matchWrap())

        val openButton = Button(this).apply {
            text = "باز کردن ربات"
            textSize = 16f
            setOnClickListener { openTelegramBot("") }
        }
        root.addView(
            openButton,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
            )
        )

        root.addView(Space(this), LinearLayout.LayoutParams(1, 0, 1f))

        val footer = TextView(this).apply {
            text = "بدون نیاز به توکن، رمز یا تنظیم اولیه"
            textSize = 13f
            gravity = Gravity.CENTER
        }
        root.addView(footer, matchWrap())

        setContentView(root)
    }

    private fun openTelegramBot(draftText: String) {
        val tgUri = Uri.parse(
            "tg://resolve?domain=${Uri.encode(BOT_USERNAME)}&text=${Uri.encode(draftText)}"
        )

        try {
            startActivity(Intent(Intent.ACTION_VIEW, tgUri))
        } catch (_: Exception) {
            val webUri = Uri.parse(
                "https://t.me/${Uri.encode(BOT_USERNAME)}?text=${Uri.encode(draftText)}"
            )
            try {
                startActivity(Intent(Intent.ACTION_VIEW, webUri))
            } catch (_: Exception) {
                Toast.makeText(this, "Telegram روی گوشی پیدا نشد.", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun extractInstagramUrl(text: String): String {
        val match = INSTAGRAM_URL.find(text) ?: return ""
        return match.value.trimEnd('.', ',', ')', ']', '}', '،')
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun matchWrap() = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.WRAP_CONTENT
    )

    companion object {
        private const val BOT_USERNAME = "Ahbe0912_bot"
        private val INSTAGRAM_URL = Regex(
            "https?://(?:(?:www|m)\\.)?instagram\\.com/[^\\s]+",
            RegexOption.IGNORE_CASE
        )
    }
}
