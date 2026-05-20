# 🏗️ FinanOS: System Architecture & Design

Welcome to **FinanOS**, an advanced Personal Finance Management System powered by AI and custom Data Structures & Algorithms (DSA). 

This document serves to explain the high-level architecture, data flow, and internal technical decisions of the project, making it easy for new contributors (or computer science professors) to understand exactly how the system was built.

---

## 1. System Design Level: The Big Picture

At its core, FinanOS operates as an **Asynchronous Monolithic Middleware**. 
It sits directly between the user (via Telegram or a Web Browser) and the ultimate source of truth (Firefly III and Market APIs). 

The system relies heavily on an **Event-Driven Architecture**:
- It listens for webhooks/polling events from Telegram.
- It translates unstructured user intent into structured JSON payloads using Google Gemini AI.
- It interacts with 3rd-party services (Crypto, Stock, Forex APIs).
- It executes accounting commands on a headless Firefly III instance.

### 🗄️ Database Strategy (Dual Database)
FinanOS utilizes a split-database strategy to optimize speed and preserve financial integrity:
1. **Firefly III (Primary Ledger)**: The remote/local SQL database managed exclusively by the Firefly III API. It holds all canonical financial data (Accounts, Transactions, Balances).
2. **Local SQLite (`finanos.db`) (Cache & State)**: A local lightweight relational database managed by SQLAlchemy. It stores:
   - **Holdings**: Specific metadata for stocks and crypto that Firefly doesn't natively track well.
   - **Activity Logs**: Raw history of bot interactions.
   - **Debt Terms**: Custom due dates and interest rates attached to specific people.

---

## 2. Core Workflow & Data Flow

How does data travel from the user's phone to the financial ledger? 

### The User Interaction Flow
1. **Input**: The user opens the Telegram Bot and types a natural language message: *"I just bought 5 shares of AAPL for 180 USD using my BIDV account."*
2. **State Machine Activation**: The `python-telegram-bot` **ConversationHandler** intercepts the message and identifies the current state of the user. 
3. **AI Parsing & Routing**:
   - The string is passed to `app/utils/parsers.py`.
   - The backend retrieves an API key from the **Round-Robin Distributor** and hits the Google Gemini Flash AI.
   - Gemini extracts the entities: `Asset: AAPL`, `Qty: 5`, `Price: 180`, `Currency: USD`, `Source: BIDV`.
4. **Market & Currency Conversion**:
   - The system checks the local **Hashtable Cache** for the USD to VND exchange rate. If expired, it queries the Forex API.
   - The 180 USD is converted into the system's `DEFAULT_CURRENCY` (e.g., VND).
5. **Headless Execution**:
   - The system queries Firefly III: *"Does the BIDV account exist?"* If not, it creates it dynamically.
   - A perfectly structured double-entry accounting payload is pushed to the Firefly III API via HTTP POST.
6. **In-Memory Logging**:
   - The transaction success is written to SQLite.
   - The log is simultaneously pushed into an **In-Memory Bounded FIFO Queue**, instantly updating the Web Dashboard without triggering an expensive database read.
7. **Feedback**: The bot replies to the user with a formatted markdown receipt.

---

## 3. Data Structures & Algorithms (DSA) Integrations

This project relies on core computer science algorithms to optimize performance and improve the user experience:

### A. Smith-Waterman Algorithm (Dynamic Programming)
- **Use Case**: **Fuzzy Finding** for CS2 Market items.
- **Why**: There are over 20,000 CS2 skins with complex names (e.g., *AK-47 | Redline (Field-Tested)*). If a user types "ak47 redline", the system builds a scoring matrix to find the optimal local sequence alignment, returning the exact item ID from the local database without needing an exact string match.

### B. Min-Heap (Priority Queue)
- **Use Case**: **Debt & Liability Sorting**.
- **Why**: When generating the "View Vault" Net Worth report, debts must be addressed strategically. The system pushes all liabilities into a Min-Heap weighted by their *Interest Rate* or *Due Date urgency*. When popped, the highest-risk financial threats are forced to the top of the user's dashboard.

### C. Bounded FIFO Queue (Linked List)
- **Use Case**: **High-Speed Activity Feed**.
- **Why**: Polling the SQLite database 50 times a minute to render the Web Dashboard's activity feed is inefficient ($O(N)$ DB read). Instead, a custom Linked-List Queue maintains a strict bound of 50 items in Random Access Memory (RAM). New transactions are `.enqueue()`'d, and if the limit is breached, the oldest is `.dequeue()`'d in $O(1)$ time. 

### D. Round-Robin Distribution (Modulo Arithmetic)
- **Use Case**: **AI Rate Limiting Evasion**.
- **Why**: Free-tier Gemini API keys have strict requests-per-minute limits. The `GeminiDistributor` takes an array of keys and uses `_current_index % array.length` to cycle evenly through the keys on every single request, ensuring perfect load balancing.

### E. Hashtable Caching
- **Use Case**: **Forex and Live Price Caching**.
- **Why**: Calling remote APIs for live stock/crypto prices is slow and expensive. The system uses a standard Dictionary (Hashtable) mapping `Asset_Ticker -> Price_Object (with TTL timestamp)`. It allows $O(1)$ lookups for rapid portfolio valuation.

---

## 4. Technology Stack Summary

| Layer | Tool / Technology | Purpose |
|-------|-------------------|---------|
| **Frontend UI** | HTML5, Vanilla JS, CSS3 | Real-time Web Dashboard (No heavy frameworks required) |
| **Backend Server** | FastAPI, Uvicorn | High-performance asynchronous API routing |
| **Chat Interface** | python-telegram-bot | Managing the complex Finite State Machine (ConversationHandler) |
| **Intelligence** | Google Gemini (`google.genai`) | Parsing unstructured human financial requests |
| **Core Database** | Firefly III (REST API) | Double-entry accounting engine & primary ledger |
| **State Database** | SQLite, SQLAlchemy ORM | Local caching, persistent logs, and holding trackers |

---

*This architecture ensures that FinanOS remains highly resilient, mathematically sound, and incredibly fast, heavily relying on academic DSA concepts deployed in a production environment.*
