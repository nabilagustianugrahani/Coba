# OpenCode Powerful Config

5 agents: build / plan / test / fix / review
- All use opencode/minimax-m3-free (free, no API key)
- Token-efficient prompts (200-800 token caps)
- Read parallel, edit minimally, no webfetch

## Swarm
```bash
.opencode/swarm/coordinate.sh 3 /tmp/task.md
```
Spawns 3 build agents in parallel, 5s stagger, logs to .opencode/logs/session-*.log

## Token tips
- minimax-m3-free is rate-limited (RPM, daily)
- Use single agent for sequential work
- Use swarm (3-5) for truly independent files
- 5-10s stagger between spawns
