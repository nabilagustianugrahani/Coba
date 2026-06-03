# Affiliator Agent

## Role
Matching scripts to affiliate products from Shopee/Tokopedia. Injects affiliate links naturally into scripts using product-aware injection.

## Handles Messages
| msg_type | Trigger | Action |
|----------|---------|--------|
| `match_products` | orchestrator | Search products → match to scripts → inject affiliate links |

## Sends Messages
- `affiliate_done` → orchestrator

## Tools
- `Affiliator` — product search, catalog management, smart link injection
- Uses script context to find best product fit per script
- Saves product catalog for cross-campaign reuse

## Config
```yaml
max_concurrent: 2
poll_interval: 1.0
search_limit: 10
```
