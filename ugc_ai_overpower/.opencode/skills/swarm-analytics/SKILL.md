# Analytics Agent

## Role
Tracks all campaign performance, generates daily reports, and monitors swarm health.

## Handles Messages
| msg_type | Trigger | Action |
|----------|---------|--------|
| `request_report` | CLI/orchestrator | Return live analytics (campaign, queue, bus health) |
| `daily_report` | orchestrator | Log incoming report (passive listener) |

## Self-Triggered (tick)
- Every 24h: `_daily_report()` — aggregates campaign stats, queue depth, agent health
- Broadcasts `daily_report` to all agents

## Data Sources
| Source | What |
|--------|------|
| `ContentBankV2` | Total content produced, per-campaign breakdown |
| `ContentQueue` | Queue depth, pending/processed counts |
| `MessageBus.health()` | Message throughput, failure rates |

## Report Format
```json
{
  "date": "2026-06-03",
  "campaigns": {"total_content": 150},
  "queue": {"pending": 5, "done": 145},
  "agents": {"pending": 0, "processing": 1, "done": 200, "failed": 2}
}
```

## Config
```yaml
poll_interval: 60.0
report_interval_hours: 24
```
