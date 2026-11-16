import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clearCookies, jsonResponse, stubFetch } from "@/test/utils";
import { api, ApiError, errorMessage } from "./api";

async function failure(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p;
  } catch (e) {
    return e as ApiError;
  }
  throw new Error("expected the request to fail");
}

const headersOf = (init: RequestInit) => (init.headers ?? {}) as Record<string, string>;

beforeEach(() => clearCookies());
afterEach(() => {
  vi.unstubAllGlobals();
  clearCookies();
});

describe("api: request shape", () => {
  it("sends GET without a CSRF header, with same-origin credentials", async () => {
    document.cookie = "csrf_token=abc123; path=/";
    const f = stubFetch(() => jsonResponse({ ok: true }));
    await api("/clients/");
    const [url, init] = f.mock.calls[0];
    expect(url).toBe("/api/v1/clients/");
    expect(init.method).toBe("GET");
    expect(init.credentials).toBe("same-origin");
    expect(headersOf(init)["X-CSRF-Token"]).toBeUndefined();
    expect(init.body).toBeUndefined();
  });

  it.each(["POST", "PATCH", "PUT", "DELETE"])("adds the CSRF header on %s", async (method) => {
    document.cookie = "csrf_token=tok%20en; path=/";
    const f = stubFetch(() => jsonResponse({}));
    await api("/x/", { method, body: method === "DELETE" ? undefined : { a: 1 } });
    expect(headersOf(f.mock.calls[0][1])["X-CSRF-Token"]).toBe("tok en");
  });

  it("sends JSON bodies with a content type, and none without a body", async () => {
    document.cookie = "csrf_token=t; path=/";
    const f = stubFetch(() => jsonResponse({}));
    await api("/x/", { method: "POST", body: { name: "A" } });
    await api("/y/", { method: "POST" });
    expect(headersOf(f.mock.calls[0][1])["Content-Type"]).toBe("application/json");
    expect(f.mock.calls[0][1].body).toBe('{"name":"A"}');
    expect(headersOf(f.mock.calls[1][1])["Content-Type"]).toBeUndefined();
  });

  it("returns an empty object for 204", async () => {
    stubFetch(() => jsonResponse(null, 204));
    await expect(api("/x/", { method: "DELETE" })).resolves.toEqual({});
  });

  it("returns parsed JSON on success", async () => {
    stubFetch(() => jsonResponse({ id: 7 }));
    await expect(api<{ id: number }>("/x/")).resolves.toEqual({ id: 7 });
  });
});

describe("api: error envelope", () => {
  it("flattens {error:{code,message,fields}} into status, code, detail and field errors", async () => {
    stubFetch(() =>
      jsonResponse({ error: { code: "validation_error", message: "Fix the form.", fields: { email: ["Someone already uses this email."], phone: "Bad phone" } } }, 400),
    );
    const err = await failure(api("/users/"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.code).toBe("validation_error");
    expect(err.message).toBe("Fix the form.");
    expect(err.fieldErrors()).toEqual({ email: "Someone already uses this email.", phone: "Bad phone", detail: "Fix the form." });
  });

  it("falls back to err.generic when the envelope has no message", async () => {
    stubFetch(() => jsonResponse({ error: { code: "x" } }, 500));
    const err = await failure(api("/x/"));
    expect(err.message).toBe("err.generic");
    expect(err.code).toBe("x");
  });

  it("copes with a non-JSON error body", async () => {
    stubFetch(() => new Response("<html>boom</html>", { status: 502 }));
    const err = await failure(api("/x/"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(502);
    expect(err.message).toBe("err.generic");
  });

  it("errorMessage returns the ApiError message or the fallback", () => {
    expect(errorMessage(new ApiError(400, { error: { message: "Nope." } }))).toBe("Nope.");
    expect(errorMessage(new Error("raw"), "err.loadList")).toBe("err.loadList");
    expect(errorMessage("weird")).toBe("err.generic");
  });
});

describe("api: 401 handling", () => {
  it("refreshes once and retries the original request", async () => {
    document.cookie = "csrf_token=t; path=/";
    let first = true;
    const f = stubFetch((url) => {
      if (url.endsWith("/auth/refresh/")) return jsonResponse({}, 200);
      if (first) {
        first = false;
        return jsonResponse({ error: { code: "not_authenticated", message: "x" } }, 401);
      }
      return jsonResponse({ ok: 1 });
    });
    const signedOut = vi.fn();
    window.addEventListener("innovation:signed-out", signedOut);
    await expect(api("/clients/")).resolves.toEqual({ ok: 1 });
    window.removeEventListener("innovation:signed-out", signedOut);
    expect(f.mock.calls.map((c) => c[0])).toEqual(["/api/v1/clients/", "/api/v1/auth/refresh/", "/api/v1/clients/"]);
    expect(f.mock.calls[1][1].method).toBe("POST");
    expect(headersOf(f.mock.calls[1][1])["X-CSRF-Token"]).toBe("t");
    expect(signedOut).not.toHaveBeenCalled();
  });

  it("announces an expired session when the refresh is refused, with a single refresh attempt", async () => {
    document.cookie = "csrf_token=t; path=/";
    const f = stubFetch(() => jsonResponse({ error: { code: "not_authenticated", message: "Expired" } }, 401));
    const signedOut = vi.fn();
    window.addEventListener("innovation:signed-out", signedOut);
    const err = await failure(api("/clients/"));
    window.removeEventListener("innovation:signed-out", signedOut);
    expect(err.status).toBe(401);
    expect(signedOut).toHaveBeenCalledTimes(1);
    expect(f.mock.calls.filter((c) => String(c[0]).endsWith("/auth/refresh/"))).toHaveLength(1);
  });

  it("does not try to refresh when nobody is signed in (no CSRF cookie)", async () => {
    const f = stubFetch(() => jsonResponse({ error: { message: "no" } }, 401));
    const signedOut = vi.fn();
    window.addEventListener("innovation:signed-out", signedOut);
    await api("/clients/").catch(() => {});
    window.removeEventListener("innovation:signed-out", signedOut);
    expect(f).toHaveBeenCalledTimes(1);
    expect(signedOut).toHaveBeenCalledTimes(1);
  });

  it("stays quiet on a 401 when quiet401 is set (session check at page load)", async () => {
    const f = stubFetch(() => jsonResponse({ error: { message: "no" } }, 401));
    const signedOut = vi.fn();
    window.addEventListener("innovation:signed-out", signedOut);
    const err = await failure(api("/auth/me/", { quiet401: true }));
    window.removeEventListener("innovation:signed-out", signedOut);
    expect(err.status).toBe(401);
    expect(signedOut).not.toHaveBeenCalled();
    expect(f).toHaveBeenCalledTimes(1);
  });

  it("does not refresh or announce for sign-in calls (auth: false)", async () => {
    document.cookie = "csrf_token=t; path=/";
    const f = stubFetch(() => jsonResponse({ error: { message: "Wrong email or password." } }, 401));
    const signedOut = vi.fn();
    window.addEventListener("innovation:signed-out", signedOut);
    const err = await failure(api("/auth/login/", { method: "POST", body: {}, auth: false }));
    window.removeEventListener("innovation:signed-out", signedOut);
    expect(err.message).toBe("Wrong email or password.");
    expect(f).toHaveBeenCalledTimes(1);
    expect(signedOut).not.toHaveBeenCalled();
  });

  it("shares a single refresh between concurrent 401s", async () => {
    document.cookie = "csrf_token=t; path=/";
    const seen = new Set<string>();
    const f = stubFetch((url) => {
      if (url.endsWith("/auth/refresh/")) return jsonResponse({});
      if (!seen.has(url)) {
        seen.add(url);
        return jsonResponse({ error: { message: "x" } }, 401);
      }
      return jsonResponse({ url });
    });
    const [a, b] = await Promise.all([api("/a/"), api("/b/")]);
    expect(a).toEqual({ url: "/api/v1/a/" });
    expect(b).toEqual({ url: "/api/v1/b/" });
    expect(f.mock.calls.filter((c) => String(c[0]).endsWith("/auth/refresh/"))).toHaveLength(1);
  });
});

describe("api: network failure", () => {
  it("turns a rejected fetch into ApiError status 0 with err.network", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const err = await failure(api("/clients/"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
    expect(err.message).toBe("err.network");
  });

  it("does not announce a signed-out session on a network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    const signedOut = vi.fn();
    window.addEventListener("innovation:signed-out", signedOut);
    await api("/clients/").catch(() => {});
    window.removeEventListener("innovation:signed-out", signedOut);
    expect(signedOut).not.toHaveBeenCalled();
  });
});

describe("ApiError.fieldErrors", () => {
  it("takes the first message of each list and skips empty values", () => {
    const e = new ApiError(400, { error: { code: "v", message: "m", fields: { a: ["first", "second"], c: 5, d: "" } } });
    const out = e.fieldErrors();
    expect(out.a).toBe("first");
    expect(out.d).toBeUndefined();
    expect(out.c).toBeUndefined();
  });
});
