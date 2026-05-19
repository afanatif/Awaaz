# Awaz Pipeline — From Scratch Run Guide

This guide walks you through starting the entire Awaz multi-agent intelligence pipeline from a clean slate (all terminals closed).

---

## Prerequisites

- **Python 3.9+** installed
- **Node.js 18+** installed (for frontend)
- **Flutter SDK** installed (for mobile app)
- **Android Studio** with Android SDK and emulator (for mobile app)
- **Gemini API key** (set as `GEMINI_API_KEY` environment variable)
- Optional: **HuggingFace API key** (set as `HF_API_KEY` for fallback)

---

## Step 1: Backend Server

Open a new terminal in the project root:

```powershell
cd d:\Hackathon\Launchmind-Agentic

# Set environment variables
$env:AWAZ_HOST='0.0.0.0'
$env:AWAZ_PORT='5050'
$env:GEMINI_API_KEY='your_gemini_key_here'
# Optional fallback
$env:HF_API_KEY='your_hf_key_here'

# Start the server
python server.py
```

The backend will start on `http://0.0.0.0:5050`. Keep this terminal open.

---

## Step 2: Web Frontend

Open a new terminal:

```powershell
cd d:\Hackathon\Launchmind-Agentic\frontend

# Start the web frontend (assumes you have a static file server or use Python's built-in)
python -m http.server 3000
```

Open your browser to `http://localhost:3000` and you should see the Awaz web interface.

---

## Step 3: Mobile Flutter App (Optional)

### 3.1 Start Android Emulator

Open Android Studio → Device Manager → Start your emulator (e.g., `Pixel_7`).

Or from terminal:

```powershell
C:\src\flutter\bin\flutter.bat emulators --launch Pixel_7
```

### 3.2 Build and Run Flutter App

Open a new terminal:

```powershell
cd d:\Hackathon\Launchmind-Agentic\mobile_flutter

# Clean and get dependencies
C:\src\flutter\bin\flutter.bat clean
C:\src\flutter\bin\flutter.bat pub get

# Run on emulator (use 10.0.2.2 to reach host machine from Android emulator)
C:\src\flutter\bin\flutter.bat run -d emulator-5554 --dart-define=AWAZ_BASE_URL=http://10.0.2.2:5050
```

The app will build, install on the emulator, and launch automatically.

---

## Step 4: Test the Pipeline

### From Web Frontend

1. Open `http://localhost:3000`
2. Type a business claim in the text input (e.g., "investing in silver is a good idea")
3. Click **Send**
4. Watch the agents run and see the verdict, source intelligence, and strategist narrative

### From Mobile App

1. On the emulator, tap the text input
2. Type a claim
3. Tap **Send**
4. Observe the pipeline execution and detailed per-source reasoning

---

## Troubleshooting

### Backend won't start (port in use)

If you see `Only one usage of each socket address`, change the port:

```powershell
$env:AWAZ_PORT='5051'
python server.py
```

Then update frontend/mobile `AWAZ_BASE_URL` accordingly.

### Flutter build fails (Kotlin incremental cache)

If you see incremental cache errors in `record_android`:

1. Edit `mobile_flutter/android/gradle.properties`
2. Add: `kotlin.incremental=false`
3. Run: `flutter clean` then retry

### Emulator can't reach backend

Ensure backend is bound to `0.0.0.0` (not just `127.0.0.1`) so the emulator can reach it via `10.0.2.2`.

### No sources are fetched

Check that your `NEWSAPI_KEY` and other API keys are set, or confirm fallbacks are working (logs will show fallback messages).

---

## Architecture Overview

- **Ingestion Agent**: Transcribes voice, extracts intent/keywords, fetches sources in parallel
- **Analyst Agent**: Contradiction detection, source evidence, reasoning, verdict
- **Strategist Agent**: Generates action chain with "what/why/based on what" reasoning
- **Executor Agent**: Simulates action execution with retries
- **Monitor Agent**: Computes outcome metrics and bilingual summaries

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `AWAZ_HOST` | `0.0.0.0` | Backend bind address |
| `AWAZ_PORT` | `5050` | Backend port |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `HF_API_KEY` | — | HuggingFace fallback API key |
| `NEWSAPI_KEY` | — | NewsAPI key (optional, has fallback) |
