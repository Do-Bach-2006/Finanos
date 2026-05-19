# FinanOS 🧠💼

FinanOS is an advanced, AI-powered Personal Finance Management System. It seamlessly bridges natural-language Telegram interactions with a real-time web dashboard and Firefly III integration. 

Powered by custom Data Structures and Algorithms (DSA) and Google's Gemini AI, FinanOS automatically parses your daily spending, calculates cross-currency transfers, tracks real-time stock/crypto prices, and provides actionable financial insights.

---

## ✨ Key Features
- **🤖 AI Natural Language Processing**: Just tell the bot "I bought 15 USD of coffee" and it handles the currency conversion, categorization, and backend logging.
- **📈 Live Market Tracking**: Real-time integrations with CoinGecko, Finnhub, and Steam for live Crypto, Stock, and CS2 skin portfolio valuations.
- **🦋 Firefly III Integration**: Headless syncing pushes all transactions natively to your self-hosted Firefly III instance.
- **⚡ Custom DSA Backbone**:
  - **Fuzzy Finding (Smith-Waterman)**: Lightning-fast local search for CS2 items.
  - **Priority Queue (Min-Heap)**: Sorts and displays your highest-risk/highest-interest debts first.
  - **Bounded FIFO Queue**: In-memory caching for a blazing-fast dashboard activity feed.
  - **Round-Robin Load Balancing**: Seamlessly distributes requests across multiple Gemini API keys to bypass rate limits.

---

## 🚀 Setup & Installation

### 1. Prerequisites
Before starting, ensure you have:
- **Python 3.9+** installed.
- A **Telegram Bot Token** (Get one from [@BotFather](https://t.me/BotFather)).
- A **Gemini API Key** (Get from [Google AI Studio](https://aistudio.google.com/)).
- A **Firefly III** instance running (Local or cloud-hosted).

### 2. Clone and Install
Clone the repository and install the required dependencies inside a virtual environment.
```bash
git clone https://github.com/your-username/finanos.git
cd finanos

# Create and activate virtual environment
python -m venv local_env
source local_env/bin/activate  # On Windows use: local_env\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration (`.env`)
Create a `.env` file in the root directory. You can copy the structure below:

```env
APP_ENV=local
DATABASE_URL=sqlite:///finanos.db
DEFAULT_CURRENCY=VND

# Intelligence (Supports multiple keys separated by commas for Round-Robin Load Balancing)
GEMINI_API_KEY=AIzaSy...key1,AIzaSy...key2

# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxyz

# Firefly III API Link
FIREFLY_BASE_URL=http://192.168.x.x/
FIREFLY_TOKEN=your_firefly_personal_access_token_here
```

### 4. Firefly III Setup
FinanOS relies on Firefly III to act as the ultimate ledger source of truth.
1. Log into your Firefly III dashboard.
2. Navigate to **Options** ➡️ **Profile** ➡️ **OAuth**.
3. Under **Personal Access Tokens**, click **Create New Token**.
4. Copy the long token string and paste it into `FIREFLY_TOKEN` in your `.env` file.
> [!NOTE]
> FinanOS is smart! If you instruct the bot to transfer money to a new account (e.g., "Paypal"), it will automatically query Firefly III and create the Asset account for you if it doesn't already exist.

---

## 💻 Running the System

Start the entire system (FastAPI Dashboard + Telegram Bot) with a single command:

```bash
python server.py
```

- **Telegram Bot**: Open Telegram, search for your bot, and send `/start`. You can immediately begin logging expenses, debts, or asset purchases.
- **Web Dashboard**: Open your browser and navigate to `http://localhost:8000`. Here you can view your Live Net Worth, dynamic Activity Feed (powered by the custom Queue), and request AI Financial Insights.

---

## ⚙️ Advanced Configuration (Web UI)
You do not need to restart the server to change API keys! 
Go to the **System & Preferences** tab on the Web Dashboard (`http://localhost:8000`) to dynamically update your:
- Base default currency.
- Preferred Market Providers (CoinGecko, Finnhub, etc.).
- Gemini API Keys (The backend will hot-reload the Round-Robin distributor instantly).

---

> [!TIP]
> **Pro-Tip on API limits:** If you hit the free-tier limit on Gemini, just generate another key on a different Google account and add it to your `.env` string with a comma. The custom `GeminiDistributor` will automatically rotate them!
