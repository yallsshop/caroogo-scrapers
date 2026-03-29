# CLAUDE.md

## Project Overview

**caroogo-scrapers** is a Python-based vehicle inventory scraping and CRM data management system for automobile dealerships. It scrapes vehicle listings from multiple dealer websites, enriches data with market intelligence from CarGurus, and syncs everything to a Supabase PostgreSQL database. A companion Chrome extension provides in-browser AI features for CRM users.

## Repository Structure

```
caroogo-scrapers/
├── scrapers/                    # Platform-specific scraper implementations
│   ├── base.py                  # BaseScraper class (all scrapers inherit from this)
│   ├── bill_collins.py          # Bill Collins Ford (DealerOn API)
│   ├── collins_nissan.py        # Collins Nissan (Apollo/Velocity)
│   └── cargurus.py              # CarGurus market data enrichment
├── main_scraper.py              # Entry point / orchestrator
├── caroogocrm_scraper.py        # Universal CRM API scraper (base44.app)
├── scraper.py                   # Caroogo VehicleSearch API scraper
├── inventory_scraper.py         # Simplified scraper (runs in CI)
├── caroogo-extension/           # Chrome extension (Manifest V3)
│   ├── manifest.json
│   ├── background/background.js # Service worker, token storage
│   ├── content/content.js       # Token interception via fetch/XHR hooks
│   ├── content/sync.js          # Localhost communication
│   └── popup/popup.js           # AI features UI
├── .github/workflows/
│   └── scraper.yml              # GitHub Actions: runs inventory_scraper.py 2x/day
├── requirements.txt             # Python dependencies
├── test_billcollins.py          # Tests for Bill Collins scraper
├── test_caroogo.py              # Tests for Caroogo scraper
├── crm-agents-blueprint.md      # Gemini 3 AI agents architecture doc
├── Api Endpoints                # Reverse-engineered Caroogo CRM API docs
├── Scraping Database Design     # Database schema design doc
└── Walkthrough                  # Deal modification API walkthrough
```

## Tech Stack

- **Language**: Python 3.12
- **HTTP Client**: `httpx` (synchronous usage)
- **HTML Parsing**: `beautifulsoup4`
- **Database**: Supabase (PostgreSQL) via `supabase` Python SDK
- **Auth/Crypto**: `PyJWT`, `cryptography`
- **Retry Logic**: `tenacity`
- **Env Management**: `python-dotenv`
- **CI/CD**: GitHub Actions (cron schedule)
- **Chrome Extension**: Vanilla JS, Manifest V3

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the main orchestrator
python main_scraper.py

# Run with CarGurus market enrichment
python main_scraper.py --enrich-cargurus

# Run the simplified inventory scraper (what CI uses)
python inventory_scraper.py

# Run individual scrapers directly
python caroogocrm_scraper.py
python scraper.py

# Run tests
python test_billcollins.py
python test_caroogo.py
```

## Environment Variables

Required environment variable (set in `.env` locally or via GitHub Secrets in CI):

- `SUPABASE_SERVICE_ROLE_KEY` - Supabase service role key for database access

The Supabase URL is hardcoded: `https://hwferrqmgqcvqfsqsjmp.supabase.co`

## Architecture & Patterns

### Scraper Pattern

All scrapers follow the **BaseScraper** inheritance pattern:

1. `BaseScraper` (in `scrapers/base.py`) provides shared methods: `upsert_vehicle()`, `update_pricing()`, `update_media()`
2. Each platform scraper extends `BaseScraper` and implements a `scrape()` method
3. Initialization requires a `supabase` client, `dealer_id`, and `dealer_name`

### Data Flow

```
Dealer websites/APIs → Python scrapers → Supabase DB
                                              ↓
                        CarGurus enrichment (optional)
                                              ↓
                        Chrome Extension ↔ Caroogo CRM
```

### Key Conventions

- **VIN is the primary unique key** for vehicle deduplication (upsert on `vin`)
- **Deduplication**: Scrapers track `seen_vins` sets to prevent processing duplicates
- **Pagination**: Page-based with vehicle count checks per page
- **Condition normalization**: "new" → "New", "cpo/certified" → "CPO", else → "Used"
- **VIN extraction regex**: `[A-HJ-NPR-Z0-9]{17}`
- **Year extraction regex**: `20\d{2}` from title/name fields
- **Error handling**: try/except with print-based logging, graceful failures (never crash the run)

### Database Tables

- `dealerships` - Dealer metadata
- `vehicles` - Core vehicle records (keyed by VIN)
- `vehicle_pricing` - Current pricing data
- `vehicle_media` - Photos/media (cleared and re-inserted on each scrape)
- `vehicle_price_history` - Historical pricing from CarGurus enrichment

## CI/CD

GitHub Actions workflow (`.github/workflows/scraper.yml`):
- **Schedule**: Runs at 8:00 UTC and 20:00 UTC (3 AM/3 PM EST)
- **Manual trigger**: Available via `workflow_dispatch`
- **Runtime**: Python 3.12 on Ubuntu, 10-minute timeout
- **Script**: Runs `inventory_scraper.py`
- **Dependencies**: Only installs `httpx supabase python-dotenv` (not full requirements.txt)

## Security Notes

- Never commit `.env` files or Supabase keys
- Some files contain hardcoded Supabase anon keys as fallbacks - these should be migrated to environment variables
- The Chrome extension intercepts auth tokens from fetch/XHR requests on `caroogocrm.com` and `base44.app`

## Adding a New Scraper

1. Create a new file in `scrapers/` (e.g., `scrapers/new_dealer.py`)
2. Import and extend `BaseScraper` from `scrapers.base`
3. Implement a `scrape()` method that fetches, parses, and calls `self.upsert_vehicle()`
4. Register the scraper in `main_scraper.py` or call it standalone
5. Follow existing patterns: VIN deduplication, condition normalization, pagination handling
