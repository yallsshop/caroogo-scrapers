# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vehicle inventory scraper and CRM integration system for Bill Collins Ford/Lincoln. Pulls inventory from multiple sources (Caroogo, DealerOn, CarGurus), stores it in Supabase, and provides an AI-enhanced Chrome extension for the Caroogo CRM.

## Running Scrapers

```bash
# Install dependencies
pip install -r requirements.txt

# Primary production scraper (Caroogo VehicleSearch API)
python inventory_scraper.py

# CRM entity scraper with deduplication
python caroogocrm_scraper.py

# Wrapper that runs CRM scraper + optional CarGurus enrichment
python main_scraper.py

# Legacy scraper (Caroogo + Bill Collins DealerOn combined)
python scraper.py
```

## Environment Variables

Scripts expect these in a `.env` file or GitHub Actions secrets:
- `SUPABASE_SERVICE_ROLE_KEY` — service role key for Supabase writes

Note: the Supabase project URL (`https://hwferrqmgqcvqfsqsjmp.supabase.co`) is hardcoded in every scraper script, not read from the environment. Changing the target project requires editing the source files directly.

## Architecture

### Scraper Layers

**Root-level scripts** are the actual entry points; `scrapers/` contains a reusable class-based layer used by some of them:

| File | Source | Notes |
|------|--------|-------|
| `inventory_scraper.py` | Caroogo VehicleSearch API | Primary production script; run by CI |
| `caroogocrm_scraper.py` | CaroogoCRM entity API | Deduplication via VIN or stock number |
| `main_scraper.py` | Wraps caroogocrm_scraper | Optionally calls CarGurus enricher |
| `scraper.py` | Caroogo + Bill Collins DealerOn | Legacy; filters non-Ford new vehicles |
| `scrapers/base.py` | — | `BaseScraper` class with shared Supabase upsert methods |
| `scrapers/bill_collins.py` | DealerOn API | Uses `BaseScraper` |
| `scrapers/collins_nissan.py` | Team Velocity/Apollo | Uses `BaseScraper` |
| `scrapers/cargurus.py` | CarGurus | Enriches existing Supabase records |

### Data Flow

1. Scraper fetches paginated vehicle data from source API (50 items/page)
2. Parses fields: condition (New/CPO/Used), pricing tiers (MSRP/Internet/Vendor/Employee/Wholesale), media URLs, features
3. Upserts into Supabase in batches: `vehicles` → `vehicle_pricing` → `vehicle_media`
4. Marks vehicles absent from the latest feed as `status = 'Sold'`

### Supabase Schema

Tables: `dealerships`, `vehicles` (PK: `vin`), `vehicle_pricing` (FK: `vin`), `vehicle_media` (FK: `vin`), `vehicle_features` (FK: `vin`).

### Chrome Extension (`caroogo-extension/`)

Manifest V3 extension targeting `*.caroogocrm.com`, `*.base44.app`, and `localhost:3000`. Popup stores AI provider + API key in `chrome.storage.sync`. Content scripts inject into Caroogo CRM pages; background service worker handles messaging.

## CI/CD

`.github/workflows/scraper.yml` — runs `inventory_scraper.py` on cron (08:00 and 20:00 UTC) and on manual `workflow_dispatch`. Uses Python 3.12 with a 10-minute timeout. Only installs `httpx supabase python-dotenv` (not the full `requirements.txt`).

## Key Reference Files

- `crm-agents-blueprint.md` — comprehensive guide for Gemini 3/3.1 Pro agent setup, function declarations, and multi-turn conversation patterns for CRM automation
- `Api Endpoints` — reverse-engineered Caroogo CRM endpoints (deal CRUD, SMS, email, comments, steps-to-sale)
- `caroogo_sample.json` / `deal_api_response.json` — representative API responses for development/testing
- `Scraping Database Design` — full schema design rationale
