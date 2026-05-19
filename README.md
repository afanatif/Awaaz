# Awaz Pipeline 🎯

**A multi-agent intelligence pipeline that validates business claims against real public signals — with source-by-source contradiction reasoning, action recommendations, and a complete audit trail.**

---

## Overview

Awaz is an explainable AI system designed for high-stakes decision-making. Before you commit time, capital, or legal risk, Awaz validates claims against real public signals from multiple sources. One input in. Multi-agent verdict out.

### What It Does

- **Cross-references 8 sources**: News, Market Data, Reddit, Regulatory/Macro, Business Recorder, PSX, Dawn Business, Profit Pakistan
- **Detects contradictions**: Analyst agent identifies contradictions and provides detailed reasoning for each source
- **Generates action plans**: Strategist agent creates action chains with clear "what/why/based on what" explanations
- **Complete audit trail**: Every step is logged with timestamps, agent names, and detailed summaries
- **Real-time processing**: Watch the pipeline execute with live status updates and agent activation
- **Bilingual output**: Decision summaries available in English and Urdu

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Awaz Pipeline                             │
└─────────────────────────────────────────────────────────────────┘

Input Claim
    │
    ▼
┌─────────────────┐
│  Ingestion      │  Whisper (voice) + Gemini (intent extraction)
│  Agent          │  Parallel source fetching (8 sources)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Analyst        │  Contradiction detection per source
│  Agent          │  Source evidence + reasoning
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Strategist     │  Action chain generation
│  Agent          │  What/why/based on what explanations
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Executor       │  Action simulation with retries
│  Agent          │  Constraint evaluation
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Monitor        │  Outcome computation
│  Agent          │  Bilingual summary generation
└────────┬────────┘
         │
         ▼
    Verdict + Action Chain + Audit Trail
```

---

## Features

### 📰 Multi-Source Cross-Referencing
Awaz fetches data from 8 Pakistani business sources:
- **News**: General news articles
- **Market Data**: Financial market indicators
- **Reddit**: Community sentiment
- **Regulatory/Macro**: Government policies and economic indicators
- **Business Recorder**: Pakistani business news
- **PSX**: Pakistan Stock Exchange data
- **Dawn Business**: Dawn's business section
- **Profit Pakistan**: Pakistani financial news

### 🔍 Contradiction Detection
The Analyst agent:
- Analyzes each source against the claim
- Computes weighted contradiction scores
- Generates plain-language explanations
- Builds structured source evidence and reasoning

### 📊 Action Recommendations
The Strategist agent:
- Generates 4 actions based on verdict
- Evaluates constraints on each action
- Orders actions into dependency chains
- Provides detailed "what/why/based on what" reasoning

### 📝 Complete Audit Trail
- Every agent action is logged with timestamps
- Input/output summaries for transparency
- Filterable by agent type
- Real-time streaming to frontend

### 🎯 Real-Time Processing
- Live status banner showing pipeline state
- Agent activation visualization
- Socket.IO streaming for instant updates
- Progress indicators for each stage

### 🌐 Bilingual Output
- Decision summaries in English
- Urdu translations using Noto Nastaliq Urdu font
- RTL support for Urdu text

---

## Installation

### Prerequisites

- **Python 3.9+**
- **Node.js 18+** (for web frontend development)
- **Flutter SDK** (for mobile app)
- **Android Studio** with Android SDK and emulator (for mobile app)
- **Gemini API key** from [aistudio.google.com](https://aistudio.google.com)
- **HuggingFace API key** from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (fallback)
- **NewsAPI key** from [newsapi.org](https://newsapi.org)
- **Reddit app credentials** from [reddit.com/prefs/apps](https://reddit.com/prefs/apps)
- **Exchange Rate API key** from [exchangerate-api.com](https://exchangerate-api.com)

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/awaz-pipeline.git
cd awaz-pipeline
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
# Google Gemini (required)
GEMINI_API_KEY=your-gemini-api-key-here

# Hugging Face (fallback)
HF_API_KEY=your-huggingface-api-key-here

# NewsAPI (required)
NEWSAPI_KEY=your-newsapi-key-here

# Reddit (required)
REDDIT_CLIENT_ID=your-reddit-client-id
REDDIT_CLIENT_SECRET=your-reddit-client-secret
REDDIT_USER_AGENT=awaz-intelligence-pipeline/1.0

# Exchange Rate API (required)
EXCHANGE_RATE_API_KEY=your-exchangerate-api-key-here

# Whisper Model (optional, default: base)
WHISPER_MODEL=base

# Slack Webhook (optional)
SLACK_WEBHOOK_URL=
```

### 4. Start the Backend Server

```bash
# Set port (default 5050)
export AWAZ_PORT=5050
python server.py
```

The server will start on `http://0.0.0.0:5050`

---

## Usage

### Web Interface

1. Open your browser to `http://localhost:5050`
2. **Enter a claim** in the text input field (e.g., "investing in silver is a good idea")
3. **Or hold the microphone** to speak your claim
4. Click **Send** to start the investigation
5. Watch the agents process your claim in real-time
6. View the verdict, source intelligence, action chain, and audit trail

### Mobile App (Flutter)

#### Start Android Emulator

```bash
flutter emulators --launch Pixel_7
```

#### Build and Run

```bash
cd mobile_flutter
flutter pub get
flutter run -d emulator-5554 --dart-define=AWAZ_BASE_URL=http://10.0.2.2:5050
```

---

## Deployment

### Docker Deployment

```bash
docker build -t awaz-pipeline .
docker run -p 5050:5050 --env-file .env awaz-pipeline
```

### Docker Compose

```bash
docker-compose up -d
```

### Cloud Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment guides for:
- Railway (recommended)
- Render
- Self-hosted VPS

---

## Project Structure

```
awaz-pipeline/
├── agents/
│   ├── ingestion_agent.py      # Voice transcription, intent extraction, source fetching
│   ├── analyst_agent.py        # Contradiction detection, source reasoning
│   ├── strategist_agent.py     # Action chain generation with explanations
│   ├── executor_agent.py       # Action simulation
│   └── monitor_agent.py        # Outcome computation, bilingual summaries
├── sources/
│   ├── news_scraper.py         # News API integration
│   ├── market_scraper.py       # Yahoo Finance integration
│   ├── reddit_scraper.py       # Reddit PRAW integration
│   ├── regulatory_scraper.py   # Regulatory data scraping
│   ├── business_recorder_scraper.py  # Business Recorder scraping
│   ├── psx_scraper.py          # PSX data scraping
│   ├── dawn_business_scraper.py      # Dawn Business scraping
│   └── profit_pakistan_scraper.py    # Profit Pakistan scraping
├── frontend/
│   ├── index.html              # Web frontend
│   ├── app.js                  # Frontend logic
│   └── style.css               # Frontend styling
├── mobile_flutter/
│   ├── lib/
│   │   ├── screens/            # Flutter screens
│   │   ├── state/              # State management
│   │   ├── models/             # Data models
│   │   └── services/           # API and socket services
│   └── pubspec.yaml            # Flutter dependencies
├── server.py                   # Flask API & WebSocket backend
├── main.py                     # Pipeline orchestration
├── message_bus.py              # Inter-agent communication
├── awaz_logger.py              # Logging system
├── db.py                       # Portfolio state management
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable template
├── Dockerfile                  # Docker configuration
├── docker-compose.yml          # Docker Compose configuration
├── DEPLOYMENT.md               # Deployment guide
└── README.md                   # This file
```

---

## API Reference

### POST /api/process/text

Process a text claim.

**Request:**
```json
{
  "text": "investing in silver is a good idea"
}
```

**Response:**
```json
{
  "status": "started",
  "type": "text"
}
```

### POST /api/process/voice

Process a voice recording.

**Request:** Multipart form data with `audio` file.

**Response:**
```json
{
  "status": "started",
  "type": "voice"
}
```

### GET /api/logs

Get all pipeline logs.

**Response:** Array of log entries.

### GET /api/outcome

Get the final outcome.

**Response:** JSON outcome object.

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "awaz-backend"
}
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AWAZ_HOST` | No | Bind address (default: `0.0.0.0`) |
| `AWAZ_PORT` | No | Port (default: `5050`) |
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `HF_API_KEY` | No | HuggingFace fallback API key |
| `NEWSAPI_KEY` | Yes | NewsAPI key |
| `REDDIT_CLIENT_ID` | Yes | Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | Yes | Reddit app client secret |
| `REDDIT_USER_AGENT` | Yes | Reddit user agent string |
| `EXCHANGE_RATE_API_KEY` | Yes | Exchange rate API key |
| `WHISPER_MODEL` | No | Whisper model size (default: `base`) |
| `SLACK_WEBHOOK_URL` | No | Slack webhook for alerts |
| `FLASK_DEBUG` | No | Flask debug mode (default: `false`) |

---

## Troubleshooting

### Port Already in Use

If you see `Only one usage of each socket address` error:

```bash
# Windows
netstat -ano | findstr :5050
taskkill /F /PID <PID>

# Linux/Mac
lsof -ti:5050 | xargs kill -9
```

### Flutter Build Errors

If you encounter Kotlin incremental cache errors:

1. Edit `mobile_flutter/android/gradle.properties`
2. Add: `kotlin.incremental=false`
3. Run: `flutter clean` then retry

### Emulator Can't Reach Backend

Ensure backend is bound to `0.0.0.0` (not `127.0.0.1`) so the emulator can reach it via `10.0.2.2`.

---

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License.

---

## Acknowledgments

- **Google Gemini** for LLM reasoning
- **OpenAI Whisper** for speech-to-text
- **NewsAPI** for news data
- **Reddit PRAW** for community sentiment
- **Yahoo Finance** for market data
- **Flask & Socket.IO** for real-time communication
- **Flutter** for mobile app development

---

## Contact

For questions or support, please open an issue on GitHub.
