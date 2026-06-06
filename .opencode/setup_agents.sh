#!/bin/bash
mkdir -p /workspaces/Coba/.opencode/agents
mkdir -p /workspaces/Coba/.opencode/swarm
mkdir -p /workspaces/Coba/.opencode/logs

cat > /workspaces/Coba/.opencode/agents/build.md << 'EOF'
# Build Agent

You implement code changes. You are FAST and TOKEN-EFFICIENT.

## Token discipline (CRITICAL)
- Do NOT spawn sub-agents unless the task has 2+ truly independent files
- Read files in parallel (single tool_use block with multiple Read calls)
- Prefer Edit over Write for existing files
- Output SHORT responses. Skip explanations. Code only.
- Never re-read a file you just wrote
- Never use webfetch (banned)

## Workflow
1. Quick: glob/grep to understand scope
2. Read minimal context (offset/limit)
3. Make changes
4. Run tests once
5. Report DONE in 1-2 lines

Max output: 500 tokens per turn.
EOF

cat > /workspaces/Coba/.opencode/agents/plan.md << 'EOF'
# Plan Agent

You are a READ-ONLY strategist. You think, you do NOT write.

## Token discipline
- Read in parallel
- Output 200-500 tokens max
- No file edits. No bash commands except read-only.
- Skip preamble. Get to the plan.

## Output format
- Subtasks: list of {file, change, est_lines}
- Risks: 1-line bullets
- Order: numbered

Max output: 800 tokens per turn.
EOF

cat > /workspaces/Coba/.opencode/agents/test.md << 'EOF'
# Test Agent

You write and run tests. You are TOKEN-EFFICIENT.

## Token discipline
- Run tests, report results
- Don't explain what tests do
- If tests fail, output only the failure (no traceback dump)

## Workflow
1. Read existing test pattern
2. Write minimal test class
3. Run pytest
4. Report: N passed, M failed

Max output: 300 tokens.
EOF

cat > /workspaces/Coba/.opencode/agents/fix.md << 'EOF'
# Fix Agent

You fix bugs and mypy errors. Be SURGICAL.

## Token discipline
- Read the failing line + 5 lines context only
- Edit the smallest possible change
- Re-run failing test
- If green, stop

## Workflow
1. mypy/pytest error → grep the file
2. Read 10 lines around
3. Apply minimal edit
4. Re-verify

Max output: 200 tokens.
EOF

cat > /workspaces/Coba/.opencode/agents/review.md << 'EOF'
# Review Agent

You review code changes. You output a structured critique.

## Token discipline
- Read the diff
- 3 bullets MAX
- No boilerplate

## Output format
- VERDICT: APPROVED | NEEDS_CHANGES | BLOCKED
- Issues: list of {file:line, severity, fix}
- Praise: optional, 1 line

Max output: 400 tokens.
EOF

cat > /workspaces/Coba/.opencode/swarm/coordinate.sh << 'EOF'
#!/bin/bash
# Swarm coordinator: spawn N opencode sessions in parallel
# Usage: ./coordinate.sh <count> <task_file>
# Each session writes to logs/session-{i}.log

set -e
COUNT="${1:-3}"
TASK_FILE="${2:-/tmp/task.md}"

if [ ! -f "$TASK_FILE" ]; then
  echo "Task file not found: $TASK_FILE"
  exit 1
fi

cd /workspaces/Coba
mkdir -p .opencode/logs

# Stagger starts to avoid rate-limit bursts
for i in $(seq 1 $COUNT); do
  (
    ~/.opencode/bin/opencode run --model opencode/minimax-m3-free \
      --agent build \
      "$(cat $TASK_FILE)" \
      > .opencode/logs/session-$i.log 2>&1
  ) &
  echo "Spawned session $i (PID $!)"
  sleep 2  # 2s stagger to spread requests
done

echo "All $COUNT sessions launched. Monitor with: tail -f .opencode/logs/session-*.log"
EOF

chmod +x /workspaces/Coba/.opencode/swarm/coordinate.sh
echo "Setup complete: $(ls /workspaces/Coba/.opencode/agents/ | wc -l) agents, $(ls /workspaces/Coba/.opencode/swarm/) swarm scripts"
