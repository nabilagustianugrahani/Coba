# UGC Swarm 2.0 — Agent Configuration

## Roles

### Coordinator (Orchestrator)
- Decomposes goals into tasks via swarm_decompose
- Assigns subtasks to workers via Task tool
- Reviews output via swarm_review
- Merges completed work

### Worker (Implementer)
- Implements code changes from subtask assignments
- Uses edit, write, bash tools
- Reports progress via swarm_progress
- Files: notion_sync.py, content_bank_v2.py, main.py, seed_full_data.py

### Reviewer (Quality Gate)
- Reviews PRs/diffs via swarm_adversarial_review
- Validates against test suite
- Approves or requests changes

### Researcher (Info Gatherer)
- Explores codebase via explore agent
- Searches docs/web for implementation patterns
- Returns findings to coordinator

## Communication Protocol

### Swarm Mail (swarmmail_*)
- Init: `swarmmail_init` per agent
- Inbox: `swarmmail_inbox` to check messages
- Send: `swarmmail_send` with subject/body
- Reserve files via `swarmmail_reserve` before editing

### Hivemind (Shared Memory)
- Store learnings: `hivemind_store` for decisions/patterns
- Retrieve: `hivemind_find` before implementing
- Key types: architecture decisions, gotchas, naming conventions

### CASS (Session Search)
- Before coding: `cass_search` for similar work
- After completion: `hivemind_store` the solution

## Task Flow
1. Coordinator: swarm_decompose(goal) → subtasks
2. Coordinator: spawn workers via Task tool (swarm-worker)
3. Workers: implement, report via swarm_progress
4. Workers: swarmmail_reserve files before editing
5. Reviewers: validate via swarm_adversarial_review
6. Coordinator: merge and close

## Files & Ownership

| File | Owner | Description |
|------|-------|-------------|
| core/notion_sync.py | Coordinator | Notion DB sync, SCHEMA, auto-create |
| core/content_bank_v2.py | Worker | SQLite product/content storage |
| main.py | Worker | CLI commands, FastAPI routes |
| seed_full_data.py | Worker | Test data seeding |
| Dockerfile | Worker | Container config |
| docker-compose.yml | Worker | Multi-service orchestration |
| .github/workflows/ci.yml | Reviewer | CI pipeline |
