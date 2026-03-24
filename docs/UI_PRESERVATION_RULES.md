# UI Preservation Rules (Keep Current UI)

This project currently uses the restored Vite dashboard UI. Use these rules to prevent accidental replacement.

## Current UI Baseline

- Dashboard framework: Vite + React.
- Runtime command on mini PC: `npm run preview -- --host 0.0.0.0 --port 3000`.
- Source location: `dashboard/src/`.

## Do Not Do

- Do not switch runtime to Next.js commands (`next dev`, `next start`).
- Do not replace `dashboard/` with a different framework scaffold.
- Do not include local `dashboard/node_modules` in sync archives.

## Deployment Guardrails

- Keep `ops/restart_dashboard.sh` using Vite preview.
- Build dashboard on mini PC after sync:

```bash
cd ~/trading-bot/dashboard
npm run build
```

- Restart dashboard via script:

```bash
bash ~/trading-bot/ops/restart_dashboard.sh
```

## Post-Deploy UI Validation

- Confirm the service is up:

```bash
curl -I -s http://127.0.0.1:3000/ | head -n 1
```

- Confirm expected dashboard content loads in browser.
- Check runtime process:

```bash
ps -ef | grep -E "vite preview|next start|next dev" | grep -v grep
```

Expected:

- `vite preview` present.
- `next start` / `next dev` absent.

## Recovery If Wrong UI Is Running

1. Stop Next processes.
2. Rebuild Vite dashboard.
3. Restart using `ops/restart_dashboard.sh`.
4. Verify port 3000 HTTP 200 and correct UI content.
