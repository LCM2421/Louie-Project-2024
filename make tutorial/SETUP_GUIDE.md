# 🤖 Telegram File Feedback Bots — Make.com Import Guide
### 100% Free Stack · Telegram + Make.com + Groq

---

## 📦 What's Included

| File | Workflow | Input |
|---|---|---|
| `scenario_document_feedback.json` | Document Feedback Bot | .txt .md .pdf |
| `scenario_csv_feedback.json` | CSV Data Analysis Bot | .csv .tsv .json |
| `scenario_code_review.json` | Code Review Bot | .py .js .ts .php .java .go .rb .cs |

---

## ⚡ Step 1 — Get Your Free Groq API Key (2 min)

1. Go to **https://console.groq.com**
2. Sign up for free (no credit card)
3. Click **API Keys** → **Create API Key**
4. Copy the key — looks like: `gsk_xxxxxxxxxxxxxxxxxxxx`

**Free limits:** 14,400 requests/day · Llama 3 70B · Fast

---

## 🤖 Step 2 — Create Your Telegram Bot (2 min)

1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Follow prompts → choose a name and username
4. Copy your **bot token** — looks like: `7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
5. Open your new bot and press **Start**

---

## ⚙️ Step 3 — Import Scenario into Make.com (3 min)

1. Go to **https://make.com** → log in (free account)
2. Click **Scenarios** in the left sidebar
3. Click the **⋮ menu** (top right) → **Import Blueprint**
4. Upload one of the `.json` files
5. Click **Save**

---

## 🔧 Step 4 — Configure the Scenario (5 min)

After importing, you need to replace 3 placeholders:

### 4a. Connect your Telegram Bot
- Click the first **Telegram** module (Watch for Messages)
- Click **Add** next to the webhook field
- Paste your **bot token** from Step 2
- Click **Save** — Make will register the webhook automatically

### 4b. Replace YOUR_BOT_TOKEN in HTTP modules
- Find any **HTTP** module that calls `api.telegram.org/file/bot{{YOUR_BOT_TOKEN}}/...`
- Replace `YOUR_BOT_TOKEN` with your actual token
- Example: `https://api.telegram.org/file/bot7123456789:AAFxxx/{{4.file_path}}`

### 4c. Replace YOUR_GROQ_API_KEY
- Find the **HTTP** module calling `api.groq.com`
- In the Headers section, find `Authorization: Bearer YOUR_GROQ_API_KEY`
- Replace `YOUR_GROQ_API_KEY` with your key from Step 1
- Example: `Authorization: Bearer gsk_xxxxxxxxxxxxxxxxxxxx`

---

## ▶️ Step 5 — Activate & Test

1. Toggle the scenario **ON** (blue switch, top left)
2. Open your Telegram bot
3. Send a file (e.g. a `.txt` document)
4. Watch Make.com execute in real time
5. Receive AI feedback in Telegram within ~10 seconds ✅

---

## 🔍 Troubleshooting

| Problem | Fix |
|---|---|
| Bot doesn't respond | Check scenario is ON · Verify webhook is set |
| "Invalid token" error | Re-paste bot token without spaces |
| Groq returns error | Check API key is correct · Verify free quota at console.groq.com |
| Message too long | Already handled — code review bot splits into 2 messages automatically |
| PDF not parsing | Telegram only exposes text-layer PDFs. For scanned PDFs, use a .txt copy |

---

## 💡 Pro Tips

- **Run all 3 bots on ONE Telegram bot** — use a single Make scenario with a Router that checks the file extension and branches to the right analysis
- **Increase context:** Groq's `llama3-70b-8192` has an 8,192 token context window — increase the substring limit from 6,000 to 8,000 chars for longer files
- **Change the AI model:** Swap `llama3-70b-8192` for `mixtral-8x7b-32768` (32K context!) for very large files
- **Add error handling:** Add a Make Error Handler module to each route that sends you a Telegram message if any step fails
- **Save to Google Sheets (free):** Add a Google Sheets module after the AI step to log all analysed files with timestamps

---

## 💰 Cost Breakdown

| Service | Cost |
|---|---|
| Make.com | Free (1,000 ops/month) |
| Telegram Bot API | Free (unlimited) |
| Groq API | Free (14,400 req/day) |
| **Total** | **$0.00 / month** |

---

*Built with Make.com · Telegram Bot API · Groq (Llama 3 70B)*
