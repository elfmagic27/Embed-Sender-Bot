# 🚀 Webhook Bot — Railway Deployment Guide

A Discord bot that lets you send **embeds** and **normal messages** to any webhook URL via slash commands — with a full dropdown embed editor, exactly like ZeoN.

---

## ✅ Commands

| Command | Description |
|---|---|
| `/webhook` | One command: enter URL → choose Embed or Message |
| `/embed_create` | Create & edit an embed with a name, then send |
| `/message_send` | Send a plain text message to a webhook directly |

---

## 🛠️ Setup

### 1. Create a Discord Bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → name it
3. Go to **Bot** tab → click **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - ✅ Message Content Intent
5. Click **Reset Token** → copy the token (you'll need this)
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Embed Links`, `Use Slash Commands`
7. Copy the generated URL and invite the bot to your server

---

### 2. Deploy to Railway

#### Option A — Deploy from GitHub (recommended)

1. Push this folder to a GitHub repo
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Select your repo
4. Railway will auto-detect Python and install `requirements.txt`

#### Option B — Railway CLI

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

---

### 3. Set Environment Variable

In your Railway project:

1. Go to your service → **Variables** tab
2. Add:

```
DISCORD_TOKEN = your-bot-token-here
```

That's it — Railway will restart the bot automatically.

---

## 📁 File Structure

```
webhook-bot/
├── bot.py            # Main bot code
├── requirements.txt  # Python dependencies
├── Procfile          # Process type for Railway
├── railway.toml      # Railway config
└── README.md         # This file
```

---

## 🎛️ How the Embed Editor Works

1. Run `/webhook <url>` or `/embed_create <name> <url>`
2. Bot shows a **dropdown** with all edit options:
   - Basic Info (title, description, color)
   - URL, Thumbnail, Image
   - Footer, Author
   - Toggle Timestamp
   - Add / Edit / Remove Field
   - Webhook URL (change it anytime)
3. Each option opens a **modal form** to fill in
4. The embed **live-updates** after every edit
5. Click **✅ Done** to send to the webhook
6. Click **✕ Cancel** to discard

---

## 🔒 Notes

- Embeds are stored **in memory** per user (cleared on bot restart)
- The editor times out after **10 minutes** of inactivity
- Max **25 fields** per embed (Discord limit)
