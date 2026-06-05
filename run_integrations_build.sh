#!/usr/bin/env bash
cd /workspaces/Coba
export PATH=$HOME/.opencode/bin:$PATH

# Write a script that runs opencode
cat > /tmp/run_opencode.sh <<'SCRIPT'
#!/usr/bin/env bash
cd /workspaces/Coba
export PATH=$HOME/.opencode/bin:$PATH
opencode run --model opencode/deepseek-v4-flash-free "Build integrations from /tmp/integrations_task.md. Read /workspaces/Coba/ugc_ai_overpower/integrations/base.py first. Create session_manager.py, social_dispatch.py, ecom_dispatch.py, modal_dispatch.py, modal_apps/{text_to_image,text_to_video,voice_synth}.py, tests. Run pytest, iterate until pass. Commit: cd /workspaces/Coba && git -c commit.gpgsign=false add -A && git -c commit.gpgsign=false commit -m 'feat(integrations)' && git push origin feat/add-sshd --force"
SCRIPT
chmod +x /tmp/run_opencode.sh

# Run in background
bash /tmp/run_opencode.sh > /tmp/integrations_build.log 2>&1 &
echo "PID: $!"
sleep 3
ps aux | grep -E 'opencode|run_opencode' | grep -v grep | head -5
