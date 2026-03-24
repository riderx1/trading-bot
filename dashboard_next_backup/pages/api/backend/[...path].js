export default async function handler(req, res) {
  const allowedMethods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"];
  if (!allowedMethods.includes(req.method || "")) {
    res.setHeader("Allow", allowedMethods.join(", "));
    return res.status(405).json({ error: "Method not allowed" });
  }

  const pathParts = Array.isArray(req.query.path) ? req.query.path : [];
  const path = pathParts.join("/");

  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(req.query)) {
    if (key === "path") continue;
    if (Array.isArray(value)) {
      for (const v of value) searchParams.append(key, v);
    } else if (value != null) {
      searchParams.append(key, value);
    }
  }

  const query = searchParams.toString();
  const hostHeaderRaw =
    req.headers["x-forwarded-host"] || req.headers.host || "";
  const hostHeader = Array.isArray(hostHeaderRaw)
    ? hostHeaderRaw[0]
    : hostHeaderRaw;
  const requestHost = hostHeader.split(":")[0] || "127.0.0.1";
  const isLocalHost = requestHost === "localhost" || requestHost === "127.0.0.1";
  const fallbackBase = isLocalHost
    ? "http://127.0.0.1:8000"
    : `http://${requestHost}:8000`;

  const backendBase =
    process.env.BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    fallbackBase;
  const target = `${backendBase}/${path}${query ? `?${query}` : ""}`;

  const contentTypeHeaderRaw = req.headers["content-type"] || "application/json";
  const contentTypeHeader = Array.isArray(contentTypeHeaderRaw)
    ? contentTypeHeaderRaw[0]
    : contentTypeHeaderRaw;

  let upstreamBody = undefined;
  if (req.method !== "GET" && req.method !== "HEAD") {
    if (typeof req.body === "string") {
      upstreamBody = req.body;
    } else if (req.body != null) {
      upstreamBody = contentTypeHeader.includes("application/json")
        ? JSON.stringify(req.body)
        : String(req.body);
    }
  }

  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers: {
        Accept: req.headers.accept || "application/json",
        "Content-Type": contentTypeHeader,
      },
      body: upstreamBody,
    });

    const body = await upstream.text();
    const contentType = upstream.headers.get("content-type") || "application/json; charset=utf-8";

    res.status(upstream.status);
    res.setHeader("Content-Type", contentType);
    return res.send(body);
  } catch (error) {
    return res.status(502).json({
      error: "Backend unreachable",
      details: error instanceof Error ? error.message : String(error),
    });
  }
}
