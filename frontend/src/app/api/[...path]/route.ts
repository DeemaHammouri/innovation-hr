import type { NextRequest } from "next/server";

/**
 * Same-origin proxy: the browser only ever talks to this app (/api/v1/...), and this handler forwards to Django.
 * That keeps the sign-in cookies first-party (no CORS, no cross-site cookies) and means Django is never exposed to the internet.
 * Cookies, the CSRF header and Set-Cookie pass through untouched; hop-by-hop headers are dropped.
 */
export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/+$/, "");
const HOP = new Set(["connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade", "host", "content-length"]);

async function forward(req: NextRequest) {
  // The path is forwarded exactly as sent, trailing slash included (Django's routes end in "/"; see skipTrailingSlashRedirect).
  const url = `${BACKEND}${req.nextUrl.pathname}${req.nextUrl.search}`;
  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP.has(key.toLowerCase())) headers.set(key, value);
  });
  const hasBody = !["GET", "HEAD"].includes(req.method);
  let upstream: Response;
  try {
    upstream = await fetch(url, {
      method: req.method,
      headers,
      body: hasBody ? await req.arrayBuffer() : undefined,
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return Response.json({ error: { code: "service_unavailable", message: "The server could not be reached." } }, { status: 502 });
  }
  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    const k = key.toLowerCase();
    if (!HOP.has(k) && k !== "set-cookie" && k !== "content-encoding") out.set(key, value);
  });
  for (const cookie of upstream.headers.getSetCookie()) out.append("set-cookie", cookie);
  return new Response(upstream.status === 204 || upstream.status === 304 ? null : upstream.body, { status: upstream.status, headers: out });
}

export { forward as GET, forward as POST, forward as PUT, forward as PATCH, forward as DELETE, forward as HEAD, forward as OPTIONS };
