# 🤖 File Feedback Bot — Complete Setup Guide

> **Beginner-friendly, step-by-step guide. Follow the phases in order.**

---

## 🗺️ The Big Picture

Before touching Make.com, understand what you're building:

```
📱 User sends file in Telegram
        ↓
🔗 Webhooks Module (receives the update)
        ↓
🔀 Router Module (checks file extension)
        ↓
┌─────────────────┬──────────────────┬─────────────────┬──────────────────┐
│   Route 1       │    Route 2       │    Route 3      │    Route 4       │
│ .txt .md .pdf   │ .csv .tsv .json  │ .py .js .ts etc │  No file sent    │
│ 4 modules       │  4 modules       │  4 modules      │  1 HTTP module   │
│ → doc review    │  → data analysis │  → code review  │  → welcome msg   │
└─────────────────┴──────────────────┴─────────────────┴──────────────────┘
        ↓                  ↓                  ↓                 ↓
  AI feedback        AI feedback        AI feedback       Welcome message
  → Telegram group   → Telegram group   → Telegram group  → Telegram group
```

### Inside each route — the 4-module pattern

Routes 1, 2 and 3 all follow the **exact same pattern**. Only the AI prompt changes.

```
HTTP 1              HTTP 2             HTTP 3            Groq 4            HTTP 5
Send "Analysing…" → getFile from    → Download file  → Native Groq AI → Send result
to your group       Telegram          content (GET)    module           to group
                    (get download URL)
```

> ✅ **Important:** Use the **native Groq module** (not HTTP) for the AI call. This avoids JSON escaping errors when file content contains special characters like Windows line endings.

**Total modules to build: 2 + 4 + 4 + 4 + 1 = 15 modules**

---

## 📋 What You Need Before Starting

| Item | Where to get it | Looks like |
|---|---|---|
| Telegram Bot Token | @BotFather on Telegram | `7123456789:AAFxxxxxxxxx` |
| Groq API Key | [console.groq.com](https://console.groq.com) | `gsk_xxxxxxxxxxxxxxxxxx` |
| Make.com account | [make.com](https://make.com) | Free tier is enough |

---

## ✅ How to Fill In HTTP Module Fields

Every HTTP module in Make.com has these fields. Here is exactly what each one means:

| Make.com Field | What to do |
|---|---|
| **Authentication type** | Always select `No authentication` |
| **URL** | Paste the full URL |
| **Method** | `POST` for most modules, `GET` for file download |
| **Headers** | Only needed if calling APIs that require auth — skip for Telegram |
| **Body content type** | Select `application/x-www-form-urlencoded` for Telegram send modules |
| **Body content type** | Select `application/json` for getFile and other Telegram API calls |
| **Parse response** | Select **Yes** on every module ✅ |

> 💡 **Why `application/x-www-form-urlencoded` for sending messages?** When sending AI output to Telegram, the response can contain special characters that break JSON. Using form-encoded key-value pairs lets Make handle encoding automatically.

---

## Phase 1 — Create Scenario, Webhook + Router

### Step 1 — Create a new scenario
Go to **Make.com → Scenarios → Create a new scenario**
Click the **big + circle** in the canvas centre.

### Step 2 — Add the Webhooks trigger
1. Search `Webhooks` → select it → choose **Custom webhook**
2. Click **Add** → name it `Telegram Hook` → click Save
3. Make shows you a URL — **copy and save it somewhere!**

```
https://hook.eu1.make.com/xxxxxxxxxxxxxxxxxx  ← save this!
```

You will need this URL in Phase 6.

### Step 3 — Add the Router
Click the **right edge arrow** of the Webhooks module → search `Router` → select **Flow Control → Router**

> ✅ Your canvas should now show: **Webhooks → Router**

---

## Phase 2 — Route 1: Documents (.txt .md .pdf)

Click the **1st route arm** coming out of the Router. Add modules in a chain.

---

### 🌐 Module 1 — Send "Analysing" message

| Field | Value |
|---|---|
| Authentication type | No authentication |
| URL | `https://api.telegram.org/botYOUR_BOT_TOKEN/sendMessage` |
| Method | POST |
| Body content type | `application/x-www-form-urlencoded` |
| Field 1 Name | `chat_id` |
| Field 1 Value | `YOUR_GROUP_CHAT_ID` |
| Field 2 Name | `text` |
| Field 2 Value | `📄 Analysing {{1.message.document.file_name}} — please wait...` |
| Parse response | Yes ✅ |

---

### 🌐 Module 2 — Get file info from Telegram

| Field | Value |
|---|---|
| Authentication type | No authentication |
| URL | `https://api.telegram.org/botYOUR_BOT_TOKEN/getFile` |
| Method | POST |
| Body content type | `application/json` |
| Body input method | `JSON string` |
| Request body | `{"file_id": "{{1.message.document.file_id}}"}` |
| Parse response | Yes ✅ |

---

### 🌐 Module 3 — Download the file

> ⚠️ Hover over Module 2 on the canvas to see its number. Replace **N** in the URL below with that number. Example: if Module 2 is numbered `7`, write `{{7.data.result.file_path}}`

| Field | Value |
|---|---|
| Authentication type | No authentication |
| URL | `https://api.telegram.org/file/botYOUR_BOT_TOKEN/{{N.data.result.file_path}}` |
| Method | GET |
| Body content type | leave empty — no body for GET |
| Parse response | Yes ✅ |

---

### 🤖 Module 4 — Groq AI (Native Module)

> ✅ Use the **native Groq module**, not an HTTP module. Search for "Groq" when adding a module and select **"Create a Chat Completion"**.

**Connection:** Click Add → paste your Groq API key from [console.groq.com](https://console.groq.com)

| Field | Value |
|---|---|
| Model | `llama-3.3-70b-versatile` |
| Max tokens returned | `1024` |
| Messages → Item 1 Role | `System` |
| Messages → Item 1 Content | *(see below)* |
| Messages → Item 2 Role | `User` |
| Messages → Item 2 Content | `{{substring(N.data; 0; 5000)}}` ← replace N with Module 3's number |

**System message content** (press Enter for real line breaks — do NOT type `\n`):
```
You are a document reviewer. Respond in plain text:

STRENGTHS:
- point

ISSUES FOUND:
- issue

SUGGESTIONS:
- suggestion

OVERALL SCORE: X/10
```

---

### 🌐 Module 5 — Send result to Telegram group

> ⚠️ Replace **G** with the Groq module's canvas number.

| Field | Value |
|---|---|
| Authentication type | No authentication |
| URL | `https://api.telegram.org/botYOUR_BOT_TOKEN/sendMessage` |
| Method | POST |
| Body content type | `application/x-www-form-urlencoded` |
| Field 1 Name | `chat_id` |
| Field 1 Value | `YOUR_GROUP_CHAT_ID` |
| Field 2 Name | `text` |
| Field 2 Value | `📄 DOCUMENT FEEDBACK` + newline + `{{1.message.document.file_name}}` + newline + newline + `{{G.result.choices[].message.content}}` |
| Parse response | Yes ✅ |

> 💡 In the Field 2 Value box, press **Enter** on your keyboard for line breaks. Reference the Groq output as `{{G.result.choices[].message.content}}` where G is the Groq module number.

---

### 🔀 Set Route 1 Filter

Right-click the **Route 1 line** (between Router and Module 1) → **Set up a filter**

| | Condition |
|---|---|
| Condition 1 | `{{1.message.document.file_name}}` Contains `.txt` |
| OR Condition 2 | `{{1.message.document.file_name}}` Contains `.md` |
| OR Condition 3 | `{{1.message.document.file_name}}` Contains `.pdf` |

> ✅ Route 1 done!

---

## Phase 3 — Route 2: Data Files (.csv .tsv .json)

Click the **2nd route arm** of the Router. Add the same modules.

**Modules 2 and 3 are identical to Route 1.** Only 3 things change:

### Module 1 — text change
| Field 2 Value | `📊 Analysing {{1.message.document.file_name}} — please wait...` |
|---|---|

### Module 4 — different Groq system message
```
You are a data analyst. Respond in plain text:

COLUMN SUMMARY:
- col: type and description

DATA QUALITY ISSUES:
- issue or None found

ANALYSIS IDEAS:
- idea 1
- idea 2

DATA QUALITY SCORE: X/10
```

### Module 5 — text change
| Field 2 Value | `📊 DATA REPORT` + newline + `{{1.message.document.file_name}}` + newline + newline + `{{G.result.choices[].message.content}}` |
|---|---|

### 🔀 Route 2 Filter

| | Condition |
|---|---|
| Condition 1 | `{{1.message.document.file_name}}` Contains `.csv` |
| OR Condition 2 | `{{1.message.document.file_name}}` Contains `.tsv` |
| OR Condition 3 | `{{1.message.document.file_name}}` Contains `.json` |

> ⚠️ **Important:** Route 2 filter must be ordered **before** Route 3 in the Router. This prevents `.csv` files from matching the `.cs` condition in Route 3.

---

## Phase 4 — Route 3: Code Files (.py .js .ts .php .java .go .rb)

Click the **3rd route arm** of the Router.

Same modules. Only 3 things change:

### Module 1 — text change
| Field 2 Value | `💻 Reviewing {{1.message.document.file_name}} — please wait...` |
|---|---|

### Module 4 — different Groq system message
```
You are a senior software engineer. Respond in plain text:

BUGS FOUND:
- bug with line number or None found

SECURITY ISSUES:
- issue or None found

CODE QUALITY:
- notes

TOP FIX:
[corrected snippet max 15 lines]

CODE SCORE: X/10
```

**User message:** `Review {{1.message.document.file_name}}: {{substring(N.data; 0; 5000)}}`

### Module 5 — text change
| Field 2 Value | `💻 CODE REVIEW` + newline + `{{1.message.document.file_name}}` + newline + newline + `{{G.result.choices[].message.content}}` |
|---|---|

### 🔀 Route 3 Filter

| | Condition |
|---|---|
| Condition 1 | `{{1.message.document.file_name}}` Contains `.py` |
| OR | Contains `.js` |
| OR | Contains `.ts` |
| OR | Contains `.php` |
| OR | Contains `.java` |
| OR | Contains `.go` |
| OR | Contains `.rb` |

> ⚠️ Do **not** add `.cs` to this filter — it would incorrectly match `.csv` files.

---

## Phase 5 — Route 4: Welcome Message

Click the **4th route arm** of the Router. Add just **1 HTTP module**.

### 🌐 Module 1 (only one) — Welcome message

| Field | Value |
|---|---|
| Authentication type | No authentication |
| URL | `https://api.telegram.org/botYOUR_BOT_TOKEN/sendMessage` |
| Method | POST |
| Body content type | `application/x-www-form-urlencoded` |
| Field 1 Name | `chat_id` |
| Field 1 Value | `YOUR_GROUP_CHAT_ID` |
| Field 2 Name | `text` |
| Field 2 Value | `👋 Welcome! Send me any file: 📄 Documents: .txt .md .pdf 📊 Data files: .csv .tsv .json 💻 Code files: .py .js .ts .php .java .go .rb` |
| Parse response | Yes ✅ |

### 🔀 Route 4 Filter

| | Condition |
|---|---|
| Condition | `{{1.message.document.file_id}}` Equal to → **(leave value empty)** |

> ✅ All 4 routes are done! Time to go live.

---

## Phase 6 — Go Live

### Step 1 — Add your bot to the Telegram group
Open your Telegram group → tap the group name → **Add Members** → search your bot username → Add it.

### Step 2 — Connect Telegram to Make (one time only)

Paste this URL into your browser. Replace both values:

```
https://api.telegram.org/botYOUR_BOT_TOKEN/setWebhook?url=YOUR_MAKE_WEBHOOK_URL
```

- `YOUR_BOT_TOKEN` = your token from @BotFather
- `YOUR_MAKE_WEBHOOK_URL` = the URL you saved in Phase 1 Step 2

You should see this in your browser:
```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

### Step 3 — Save and turn ON
1. Click **Save** in Make.com
2. Flip the **scenario toggle ON** (bottom left — turns blue)

### Step 4 — Test it
1. Send `hello` to your Telegram group → welcome message appears ✅
2. Send `employee_hr.csv` → full AI data report appears within 10 seconds 🎉
3. Send a `.py` file → code review appears ✅

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| Bot doesn't reply | Check scenario toggle is ON. Confirm setWebhook returned `"ok":true` |
| "Webhook was not set" | Make sure the Make webhook URL starts with `https://` and has no spaces |
| Empty AI response | Check Groq module — make sure you're using the native Groq module, not HTTP |
| Module number confusion | Hover over a module on the canvas — Make shows its number in the top-left corner |
| Route not triggering | Check filter conditions — use `Contains` not `Equal to` for file extensions |
| `.csv` triggering code review | Make sure Route 2 filter is ordered before Route 3 in the Router, and `.cs` is NOT in Route 3 filter |
| Bot added to group but no response | Make sure the bot has permission to read/send messages in the group |
| "Bad control character" JSON error | This happens when using HTTP module for Groq — switch to the native Groq module instead |
| Groq output not showing in Telegram | Use `{{G.result.choices[].message.content}}` — note `.result.` is required for native Groq module output |

---

## 📊 Free Tier Limits

| Service | Free allowance | Resets |
|---|---|---|
| Make.com operations | 1,000 / month | Monthly |
| Make.com active scenarios | 2 | — |
| Groq API requests | 14,400 / day | Daily |
| Telegram Bot API | Unlimited | Never |

> Each file analysis uses ~4 Make operations → **~250 analyses/month free**

---

## 📁 Repository Files

```
📦 make-tutorial
 ┣ 📄 README.md                ← you are here
 ┣ 📊 SETUP.md                 ← test file: Sample readme.md docs
 ┣ 📊 employee_hr.csv          ← test file: 60 HR records
 ┗ 📊 sample_buggy.py          ← test file: Check the codes and provide how to fix it 
```

---

*Built with Make.com · Telegram Bot API · Groq Llama 3 · $0/month*

---

## 🔍 Key Differences from v3

If you built this from a previous version of this guide, here are the important changes:

| What changed | Why |
|---|---|
| Groq module is now **native Groq** instead of HTTP | HTTP + JSON string mode breaks when file content has Windows line endings (`\r\n`) |
| Telegram send modules use `application/x-www-form-urlencoded` | Prevents AI output (with special characters) from breaking JSON body |
| `.cs` removed from Route 3 filter | `.cs` incorrectly matched `.csv` files, sending them to code review instead of data analysis |
| Groq output reference is `G.result.choices[].message.content` | Native Groq module uses `.result.` — HTTP module used `.data.` |

## ✅ Example test for this scenario

### Saying hello to the telegram group channel

<img width="416" height="248" alt="image" src="https://github.com/user-attachments/assets/cc21ede1-3b2e-462d-8a58-d55c0a3156d6" />
<img width="1030" height="607" alt="image" src="https://github.com/user-attachments/assets/918ec543-9dcc-47f9-be4f-ec0c9a871824" />

### Analysing the documentations

<img width="497" height="757" alt="image" src="https://github.com/user-attachments/assets/4ed10b19-65be-48f9-8b86-dba7983bb0dd" />
<img width="1024" height="618" alt="image" src="https://github.com/user-attachments/assets/d7b229d1-4fec-4f7a-aaed-c6791206836d" />

### Data Reporting

<img width="489" height="776" alt="image" src="https://github.com/user-attachments/assets/d1e2cf67-bc49-46bc-8ab3-a6ac1c4046ae" />
<img width="967" height="554" alt="image" src="https://github.com/user-attachments/assets/fb1079f9-d72e-4301-bcab-31795405f4d8" />

### Checking the code and give feedback how to fix it

<img width="391" height="880" alt="image" src="https://github.com/user-attachments/assets/89967841-2e5e-4527-b0a4-795a52eb0d51" />
<img width="1001" height="630" alt="image" src="https://github.com/user-attachments/assets/44a8912f-2a25-4727-a5cf-b3c2be1831f4" />




