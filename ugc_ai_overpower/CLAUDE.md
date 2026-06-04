# UGC AI Overpower — Agent Guidelines

## Project
Autonomous UGC Affiliate Marketing Swarm — Enterprise Content Factory
- Notion DB: 8 databases (Campaigns, Content, Analytics, Gallery, Inbox, Brands, Approvals, Products)
- API: Notion v2022-06-28
- Storage: SQLite via content_bank_v2.py
- AI Router: 9router (port 20128)

## Key Files
- `core/notion_sync.py` — Notion DB sync, SCHEMA, auto_create
- `core/content_bank_v2.py` — SQLite storage
- `main.py` — CLI entry point
- `seed_full_data.py` — Demo data seeder

## Commands
- Seed data: `python seed_full_data.py`
- Sync products: `python main.py notion-sync-products`
- List products: `python main.py list-products`
- Notion dashboard: `python main.py notion-status`

## Agent Protocol
See AGENTS.md in repo root for swarm communication protocol.
Use swarmmail for inter-agent communication and hivemind for shared memory.
