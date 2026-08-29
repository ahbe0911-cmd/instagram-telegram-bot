package com.ahmad.igbotshare

import android.app.Activity
import android.content.Intent
import android.graphics.Typeface
import android.net.Uri
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Space
import android.widget.TextView
import android.widget.Toast

class MainActivity : Activity() {
    private val prefs by lazy { getSharedPreferences("share_to_bot", MODE_PRIVATE) }
    private var pendingSharedText: String? = null

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
        val sharedText = if (sourceIntent.action == Intent.ACTION_SEND) {
            sourceIntent.getStringExtra(Intent.EXTRA_TEXT)?.trim().orEmpty()
        } else {
            ""
        }

        val extracted = extractInstagramUrl(sharedText)
        pendingSharedText = extracted.ifBlank { sharedText }.ifBlank { null }

        val savedBot = normalizeBotUsername(prefs.getString(KEY_BOT_USERNAME, "").orEmpty())
        if (pendingSharedText != null && savedBot.isNotBlank()) {
            openTelegramBot(savedBot, pendingSharedText!!)
            finish()
            return
        }

        showSetup(savedBot)
    }

    private fun showSetup(currentBot: String) {
        val padding = dp(24)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(padding, dp(36), padding, padding)
            layoutDirection = android.view.View.LAYOUT_DIRECTION_RTL
        }

        val title = TextView(this).apply {
            text = "دانلود با ربات"
            textSize = 26f
            setTypeface(typeface, Typeface.BOLD)
            gravity = Gravity.CENTER
        }
        root.addView(title, matchWrap())

        val description = TextView(this).apply {
            text = "نام کاربری ربات تلگرام را فقط یک بار وارد کن. بعد از آن در Instagram روی Share بزن و «دانلود با ربات» را انتخاب کن؛ مستقیم همان چت باز می‌شود و لینک آماده ارسال است."
            textSize = 16f
            gravity = Gravity.CENTER
            setPadding(0, dp(20), 0, dp(22))
        }
        root.addView(description, matchWrap())

        val botInput = EditText(this).apply {
            hint = "مثلاً MyInstagramDownloaderBot"
            setText(currentBot)
            textSize = 17f
            singleLine = true
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
            gravity = Gravity.CENTER
        }
        root.addView(botInput, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))

        val saveButton = Button(this).apply {
            text = if (pendingSharedText != null) "ذخیره و باز کردن ربات" else "ذخیره"
            textSize = 16f
            setOnClickListener {
                val username = normalizeBotUsername(botInput.text.toString())
                if (!isValidTelegramUsername(username)) {
                    Toast.makeText(
                        this@MainActivity,
                        "نام کاربری ربات معتبر نیست. @ را وارد نکن یا بگذار برنامه خودش حذف کند.",
                        Toast.LENGTH_LONG
                    ).show()
                    return@setOnClickListener
                }

                prefs.edit().putString(KEY_BOT_USERNAME, username).apply()
                Toast.makeText(this@MainActivity, "نام ربات ذخیره شد", Toast.LENGTH_SHORT).show()

                pendingSharedText?.let { text ->
                    openTelegramBot(username, text)
                    finish()
                }
            }
        }
        val buttonParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
            topMargin = dp(18)
        }
        root.addView(saveButton, buttonParams)

        if (currentBot.isNotBlank()) {
            val testButton = Button(this).apply {
                text = "باز کردن ربات"
                setOnClickListener { openTelegramBot(currentBot, "") }
            }
            val testParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT).apply {
                topMargin = dp(10)
            }
            root.addView(testButton, testParams)
        }

        root.addView(Space(this), LinearLayout.LayoutParams(1, 0, 1f))

        val footer = TextView(this).apply {
            text = "این برنامه هیچ توکن، رمز یا اطلاعات ورود تلگرام و اینستاگرام را ذخیره نمی‌کند."
            textSize = 13f
            gravity = Gravity.CENTER
        }
        root.addView(footer, matchWrap())

        setContentView(root)
    }

    private fun openTelegramBot(botUsername: String, draftText: String) {
        val tgUri = Uri.parse(
            "tg://resolve?domain=${Uri.encode(botUsername)}&text=${Uri.encode(draftText)}"
        )
        val telegramIntent = Intent(Intent.ACTION_VIEW, tgUri)

        try {
            startActivity(telegramIntent)
        } catch (_: Exception) {
            val webUri = Uri.parse(
                "https://t.me/${Uri.encode(botUsername)}?text=${Uri.encode(draftText)}"
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

    private fun normalizeBotUsername(value: String): String = value.trim().removePrefix("@").trim()

    private fun isValidTelegramUsername(value: String): Boolean =
        value.length in 5..32 && value.matches(Regex("[A-Za-z0-9_]+"))

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun matchWrap() = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.MATCH_PARENT,
        ViewGroup.LayoutParams.WRAP_CONTENT
    )

    companion object {
        private const val KEY_BOT_USERNAME = "bot_username"
        private val INSTAGRAM_URL = Regex(
            "https?://(?:(?:www|m)\\.)?instagram\\.com/[^\\s]+",
            RegexOption.IGNORE_CASE
        )
    }
}
