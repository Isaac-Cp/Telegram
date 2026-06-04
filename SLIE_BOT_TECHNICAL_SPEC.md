# SLIE Telegram Lead Generation Bot — Technical Specification

## 1. Overview
SLIE (Smart Lead Identification Engine) is a high-performance Telegram automation system designed to find, analyze, and engage with high-intent leads in the IPTV and related niches. It operates using a "Human-Mimicry" engine to ensure account safety while maximizing conversion potential.

---

## 2. Core Architecture

### A. Telegram Client Manager (`app/services/telegram_client.py`)
- **Role**: Centralized connection hub.
- **Functionality**: Manages multiple Telegram accounts using `Telethon`. It uses `StringSession` for persistence and an `asyncio.Lock` to prevent "IP conflict" errors during concurrent background task startups.
- **Rotation**: Supports rotating between multiple phone numbers to distribute load.
- **Database Integration**: Automatically seeds and tracks account health (joins, DMs, replies) in the database for real-time monitoring.

### B. Group Discovery Engine (`app/services/group_discovery/`)
- **Keyword Search**: Uses `functions.contacts.SearchRequest` to find public groups based on niche keywords (e.g., "iptv discussion").
- **Group Analyzer**: 
    - **Metadata Filter**: Rejects groups with < 200 members (adjustable for testing).
    - **Activity Filter**: Requires > 15 messages/24h and > 7 unique active users.
    - **Market Analysis**: Uses `seller_detector.py` to calculate the "Seller Density". If a group has > 35% sellers or promotional content, it is flagged as a "Seller Hub" and ignored.
    - **Join Scheduler**: Automatically joins "Approved" groups at randomized intervals to avoid anti-spam triggers.
- **Spam Detection & Filtering Mechanisms**:
    - **Promotion Detection**: Scans messages for keywords like `buy iptv`, `cheap iptv`, `panel available`, etc.
    - **Activity Analysis**: Rejects groups with < 15 messages/24h or < 7 unique active users to ensure high engagement.
    - **Identical Message Detection**: Tracks message hashes per user to detect automated spamming patterns.
    - **Market Saturation**: Calculates `seller_ratio`. Only `DISCUSSION GROUP` types are approved; `SELLER HUB` types are rejected.

### C. Message Scraper & Lead Scoring (`app/services/message_scraper.py` & `app/services/lead_scoring.py`)
- **Real-time Listener**: Listens to all messages in joined groups.
- **Noise Filtering**: Ignores messages < 5 characters, emoji-only messages, or URL-only messages.
- **Intent Analysis**: 
    - **NLP Classification**: Uses AI to classify messages as `complaint`, `help_request`, `general_discussion`, or `advertisement`.
    - **Predictive Buyer Engine**: Assigns scores (0-100) based on signals:
        - Complaint Signals (30 pts): "buffering", "error", "down".
        - Recommendation Requests (40 pts): "recommend", "best provider", "trial".
        - Technical Terms (20 pts): "xtream", "m3u", "panel".
        - Activity Spikes (10 pts): Frequent messaging within an hour.
- **Opportunity Engine**: Prioritizes leads based on their `opportunity_score` and `priority_level` (`HIGH`, `MEDIUM`, `LOW`).
- **Cross-Group Identity Tracking**: Boosts scores for users seen in multiple groups or with recurring complaints.
- **Sentiment Analysis**: Tracks aggregate sentiment trends (Frustrated, Interested, Questioning) for community health monitoring.

### D. Response & Human Engine (`app/services/response_engine.py` & `app/services/human_engine.py`)
- **Human Engine**: 
    - **Simulated Typing**: Applies 3–10s typing delays before sending.
    - **Active Hours**: Follows configured business hours (e.g., 08:00–20:00) with random "online" appearances.
    - **Safety Limits**: Strict daily limits (7 joins, 20 replies, 4 DMs) and randomized cooldowns.
- **DM Orchestrator**: Processes `HIGH` and `MEDIUM` leads, applying randomized delays (15–45 mins for DMs, 20 mins for public replies).
- **Persona AI**: Rotates between specialized personas (e.g., "Aiden - Technical Architect") to generate contextual, helpful responses.
- **Persona ROI Tracking**: Monitors conversion rates and lead volume per persona to optimize outreach strategy.

---

## 3. Operational Metrics & Dashboard
- **Dashboard UI (`app/templates/slie_dashboard.html`)**:
    - **Modern Design**: Responsive "Liquid Glass" UI with 3D perspective mouse effects and claymorphism.
    - **Real-time Data Streams**:
        - **Hourly Lead Heatmap**: Visualizes peak times for lead detection.
        - **Sentiment Analysis Trends**: Tracks user emotions over time.
        - **Persona Conversion ROI**: Compares performance between different AI personas.
        - **Account Health & Safety**: Real-time status of proxies, cooldowns, and daily limits for all connected accounts.
        - **Influence Mapping**: Categorizes users by their community impact (Leaders, Power Users, Regulars).
        - **Activity Feed**: Live log of bot actions and detected leads.
- **Backend Analytics (`app/services/dashboard.py`)**:
    - High-performance SQL queries for aggregate metrics.
    - Mock Redis implementation for environments without a live Redis server.

---

## 4. Database Schema (`app/models/`)
- **Lead**: Stores user info, intent scores, conversion stage (NEW, CONTACTED, CONVERTED), and DM history.
- **Group**: Stores discovered communities, their metadata, market type, and join status.
- **TelegramAccount**: Manages session strings, phone numbers, and account health status. Supports `TEXT` type for long session strings.
- **User**: Tracks cross-group identity, influence level, and lifetime value (LTV) scores.
- **Message**: Archive of scraped messages for historical analysis.

---

## 5. Security & Safety
- **Anti-Flood**: Implements `asyncio.sleep` between critical actions.
- **Proxy Support**: Integrates with residential proxies to mask automation signatures.
- **Device Simulation**: Mimics specific device models (e.g., "Desktop Windows 10") to blend in with regular users.
- **Fault Tolerance**: Automatic fallback to in-memory `MockRedisSync` to prevent system crashes during Redis connection failures.

---

## 6. How to Run
1.  **Environment**: Configure `.env` with `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and `TELEGRAM_SESSION_STRING`.
2.  **Database**: Ensure PostgreSQL is running or use the provided Docker/Local setup.
3.  **Server**: Run `uvicorn app.main:app --host 0.0.0.0 --port 8000` to start the dashboard.
4.  **Bot Session**: Run `python run_bot_session.py` for dedicated lead generation windows.
