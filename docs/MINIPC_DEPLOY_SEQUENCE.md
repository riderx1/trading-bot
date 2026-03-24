# Mini PC Deploy Sequence

Use this sequence to deploy from laptop to mini PC while preserving the current Vite UI.

## Primary Update Flow (Git)

Use this as the default workflow for all normal updates.

### A) On laptop: commit and push

```powershell
Set-Location C:/Users/teckt/Desktop/trading-bot
git add .
git commit -m "describe update"
git push origin master
```

### B) On mini PC: pull and restart

```bash
cd ~/trading-bot
git pull origin master
bash ~/trading-bot/ops/restart_backend.sh ~/trading-bot
bash ~/trading-bot/ops/restart_dashboard.sh
```

### C) Verify

```bash
curl -s http://127.0.0.1:8000/status
curl -I -s http://127.0.0.1:3000/ | head -n 1
```

Expected:

- `execution_mode` is `paper` in `/status`.
- Dashboard returns `HTTP/1.1 200 OK`.

## Fallback Flow (Archive Sync)

If Git pull is unavailable on mini PC, use archive sync as fallback.

## Preconditions

- SSH access works to mini PC user (default: `openclaw`).
- Mini PC project root: `/home/openclaw/trading-bot`.
- Laptop project root: local workspace root.
- Dashboard stack is Vite (not Next.js).

## 1) Sync and build (fallback)

From laptop (PowerShell):

```powershell
Set-Location C:/Users/teckt/Desktop/trading-bot
./ops/sync-to-minipc.ps1 -MiniPcHost 192.168.1.68 -MiniPcUser openclaw -InstallAndBuild
```

What this does:

1. Archives project source from laptop.
2. Copies archive to mini PC.
3. Replaces remote project files.
4. Runs dashboard build and backend dependency/setup tasks.

## 2) Restart backend and dashboard (fallback)

If the sync script restart phase fails due shell quoting, run explicit restart scripts:

```powershell
Set-Location C:/Users/teckt/Desktop/trading-bot
scp ops/restart_backend.sh openclaw@192.168.1.68:~/trading-bot/ops/restart_backend.sh
ssh openclaw@192.168.1.68 "chmod +x ~/trading-bot/ops/restart_backend.sh; ~/trading-bot/ops/restart_backend.sh ~/trading-bot"
ssh openclaw@192.168.1.68 "bash ~/trading-bot/ops/restart_dashboard.sh"
```

## 3) Verify services (fallback)

```powershell
ssh openclaw@192.168.1.68 "curl -s http://127.0.0.1:8000/status"
ssh openclaw@192.168.1.68 "curl -s http://127.0.0.1:8000/paper-trades/active"
ssh openclaw@192.168.1.68 "curl -s http://127.0.0.1:8000/performance/summary"
ssh openclaw@192.168.1.68 "curl -I -s http://127.0.0.1:3000/ | head -n 1"
```

Expected:

- API returns JSON at port 8000.
- Dashboard returns `HTTP/1.1 200 OK` at port 3000.

## 4) Optional: reset performance from now

```powershell
ssh openclaw@192.168.1.68 "curl -s -X POST 'http://127.0.0.1:8000/paper-wallets/reset?confirm=true&clear_history=true'"
```

This resets strategy wallets and clears simulated trade history/rankings.

## Operational Notes

- Preferred workflow is `git push` from laptop + `git pull` on mini PC.
- Avoid inline complex restart one-liners over SSH from PowerShell when possible.
- Prefer script-based restarts (`restart_backend.sh`, `restart_dashboard.sh`) for consistency.
- Keep deploy logs under `~/trading-bot/ops/` for troubleshooting.
