/**
 * pages/api/health.js — Next.js API route: dashboard health check
 *
 * Returns a simple JSON response so you can confirm the Next.js server
 * itself is reachable (separate from the FastAPI backend).
 *
 * GET /api/health → { status: "ok", timestamp: "..." }
 */

export default function handler(req, res) {
  res.status(200).json({
    status: "ok",
    timestamp: new Date().toISOString(),
  });
}
