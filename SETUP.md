# Eagle Events AI Bot — Setup

## 1. Slack App

1. Pojdi na https://api.slack.com/apps → Create New App → From scratch
2. Ime: `Marketinko`, izberi tvoj Eagle Events workspace → **Create App**
3. **OAuth & Permissions** → Bot Token Scopes:
   - `app_mentions:read`
   - `chat:write`
   - `im:history`
   - `im:read`
   - `reactions:write`
3. **Event Subscriptions** → Enable → Request URL: `https://YOUR_RAILWAY_URL/slack/events`
   - Subscribe to bot events: `app_mention`, `message.im`
4. Install app to workspace → kopiraj **Bot User OAuth Token** (`xoxb-...`)
5. **Basic Information** → kopiraj **Signing Secret**
6. V Slack: `/invite @eagle-events-bot` v kanal

## 2. Meta Ads API

1. https://developers.facebook.com → My Apps → Create App → Business
2. Add product: **Marketing API**
3. **Tools → Graph API Explorer** → Generate token z:
   - `ads_read`, `ads_management`, `business_management`
4. Za dolgotrajen token: `GET /oauth/access_token?grant_type=fb_exchange_token`
5. Ad Account ID najdeš v Facebook Ads Managerju (format: `act_XXXXXXXXX`)

## 3. Google Drive Service Account

1. https://console.cloud.google.com → New Project
2. Enable **Google Drive API**
3. **IAM & Admin → Service Accounts** → Create → Download JSON key
4. V Google Drive: desi z mapa za marketing → Share → dodaj service account email z Viewer pravicami
5. Kopiraj Folder ID iz URL-ja Drive mape

## 4. Deploy na Railway

```bash
cd eagle-events-bot
railway login
railway init
railway up
```

Nastavi env variables v Railway dashboard (vse iz .env.example).

## 5. Lokalno testiranje

```bash
pip install -r requirements.txt
cp .env.example .env  # izpolni vrednosti
uvicorn main:app --reload
# V drugem terminalu:
ngrok http 8000  # za Slack webhook URL
```
