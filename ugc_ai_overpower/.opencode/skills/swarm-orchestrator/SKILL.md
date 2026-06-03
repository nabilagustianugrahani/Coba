# Swarm Orchestrator Agent

## Role
**Queen Agent** — dispatches campaigns, tracks progress, coordinates all swarm agents.

## Handles Messages
| msg_type | Trigger | Action |
|----------|---------|--------|
| `campaign` | CLI/API | Decompose campaign → dispatch to script_writer |
| `scripts_ready` | script_writer | Forward to affiliator or video_producer |
| `affiliate_done` | affiliator | Forward to video_producer |
| `videos_ready` | video_producer | Forward to poster |
| `posting_done` | poster | Mark campaign complete, broadcast status |
| `agent_hello` | any agent | Register in agent registry |
| `agent_status` | any agent | Update heartbeat |
| `list_agents` | CLI | Return all registered agents + campaign count |
| `list_campaigns` | CLI | Return all campaign statuses |

## Broadcasts
- `campaign_complete` — when all posting finishes

## Tools
- `MessageBus` — SQLite-backed inter-agent queue
- `_agent_registry` — tracks all agent heartbeats
- 72h campaign timeout → auto-fail stale campaigns
- Retries failed messages up to 3× with exponential backoff

## Config
```yaml
max_concurrent: 10
poll_interval: 0.5
retry_max: 3
campaign_timeout_hours: 24
```
