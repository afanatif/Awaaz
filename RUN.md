# Quick Start Guide

Get Awaz Pipeline running in 3 simple steps.

---

## Prerequisites

- Python 3.9+
- Node.js 18+ (optional, only if you want to modify web frontend)
- Flutter SDK + Android Studio (optional, only if you want to run mobile app)
- API Keys (see Environment Variables below)

---

## Step 1: Clone & Install

```bash
git clone https://github.com/afanatif/Awaaz.git
cd Awaaz
pip install -r requirements.txt
```

---

## Step 2: Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
# Required
GEMINI_API_KEY=your-gemini-api-key
NEWSAPI_KEY=your-newsapi-key
REDDIT_CLIENT_ID=your-reddit-client-id
REDDIT_CLIENT_SECRET=your-reddit-client-secret
REDDIT_USER_AGENT=awaz-intelligence-pipeline/1.0
EXCHANGE_RATE_API_KEY=your-exchange-rate-api-key

# Optional
HF_API_KEY=your-huggingface-key
WHISPER_MODEL=base
SLACK_WEBHOOK_URL=
```

**Get API Keys:**
- Gemini: https://aistudio.google.com
- NewsAPI: https://newsapi.org
- Reddit: https://reddit.com/prefs/apps
- Exchange Rate: https://exchangerate-api.com

---

## Step 3: Run Backend

```bash
python server.py
```

The backend will start on `http://localhost:5050`

**Open your browser to:** `http://localhost:5050`

---

## Optional: Run Mobile App (Flutter)

### Start Android Emulator
```bash
flutter emulators --launch Pixel_7
```

### Run Mobile App
```bash
cd mobile_flutter
flutter pub get
flutter run -d emulator-5554 --dart-define=AWAZ_BASE_URL=http://10.0.2.2:5050
```

---

## What's Included

✅ **Backend** - Flask-SocketIO server with 5 agents  
✅ **Web Frontend** - Modern React-like UI with real-time updates  
✅ **Mobile App** - Flutter app for Android  
✅ **Docker** - Containerized deployment ready  
✅ **Railway Config** - One-click cloud deployment  

---

## Using the UI

1. **Enter a claim** - Type in the input field (e.g., "investing in silver is a good idea")
2. **Or use voice** - Hold the microphone button to speak
3. **Click Send** - Watch the agents process your claim in real-time
4. **View results** - See verdict, source intelligence, action chain, and audit trail

---

## Troubleshooting

**Port already in use?**
```bash
# Windows
netstat -ano | findstr :5050
taskkill /F /PID <PID>

# Linux/Mac
lsof -ti:5050 | xargs kill -9
```

**Flutter build errors?**
Edit `mobile_flutter/android/gradle.properties` and add:
```
kotlin.incremental=false
```

**Emulator can't reach backend?**
Ensure backend runs on `0.0.0.0` (not `127.0.0.1`) so emulator can reach it via `10.0.2.2`

---

## Deploy to Railway

1. Go to https://railway.app
2. Click "New Project" → "Deploy from GitHub repo"
3. Select `afanatif/Awaaz`
4. Add environment variables in Railway dashboard
5. Deploy

---

## Support

For detailed documentation, see [README.md](README.md) and [DEPLOYMENT.md](DEPLOYMENT.md)

---

**That's it! Your friend can now clone, install, and run Awaz Pipeline.**
