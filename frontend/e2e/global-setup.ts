import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import { API_PORT, API_URL, BACKEND_DIR, CEO, FRONTEND_DIR, STATE_FILE, SUPER_ADMIN, WEB_PORT, WEB_URL, pythonPath, type E2eState } from "./support/env";

function portBusy(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const s = net.connect({ port, host: "127.0.0.1" });
    s.once("connect", () => {
      s.destroy();
      resolve(true);
    });
    s.once("error", () => resolve(false));
  });
}

async function waitFor(url: string, what: string, ms = 120_000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try {
      const r = await fetch(url);
      if (r.status < 500) return;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`${what} did not start within ${ms / 1000}s (${url})`);
}

function newestMtime(target: string): number {
  if (!fs.existsSync(target)) return 0;
  const stat = fs.statSync(target);
  if (!stat.isDirectory()) return stat.mtimeMs;
  let newest = stat.mtimeMs;
  for (const name of fs.readdirSync(target)) {
    if (/\.test\.tsx?$/.test(name)) continue; // unit tests are not part of the app build
    newest = Math.max(newest, newestMtime(path.join(target, name)));
  }
  return newest;
}

export default async function globalSetup() {
  for (const port of [API_PORT, WEB_PORT]) {
    if (await portBusy(port)) throw new Error(`Port ${port} is already in use. The suite owns 8100 (API) and 3100 (web); stop whatever is listening there.`);
  }
  const python = pythonPath();
  if (!fs.existsSync(python) && !process.env.E2E_PYTHON) throw new Error(`Python not found at ${python}. Set E2E_PYTHON.`);

  // E2E_DB_DIR reuses a database folder (proves the suite repeats on existing data); otherwise a fresh temporary one.
  const reuse = process.env.E2E_DB_DIR;
  const dir = reuse ? path.resolve(reuse) : fs.mkdtempSync(path.join(os.tmpdir(), "innovation-e2e-"));
  fs.mkdirSync(dir, { recursive: true });
  const db = path.join(dir, "e2e.sqlite3");
  if (path.resolve(db) === path.resolve(BACKEND_DIR, "db.sqlite3")) throw new Error("Refusing to use the real database.");
  const state: E2eState = { dir, db, createdDir: !reuse, pids: [], python };
  fs.writeFileSync(STATE_FILE, JSON.stringify(state));

  const djangoEnv: NodeJS.ProcessEnv = {
    ...process.env,
    DJANGO_DB_PATH: db,
    PRIVATE_MEDIA_ROOT: path.join(dir, "private_media"),
    DJANGO_SUPERUSER_PASSWORD: SUPER_ADMIN.password,
    CEO_EMAIL: CEO.email,
    CEO_PASSWORD: CEO.password,
    CEO_NAME: "E2E Chief Executive",
    PYTHONIOENCODING: "utf-8",
    PYTHONUTF8: "1",
  };
  delete djangoEnv.DJANGO_SETTINGS_MODULE; // always the development settings: seed_demo_data needs DEBUG
  const manage = (...args: string[]) => {
    const r = spawnSync(python, ["manage.py", ...args], { cwd: BACKEND_DIR, env: djangoEnv, encoding: "utf8" });
    if (r.status !== 0) throw new Error(`manage.py ${args.join(" ")} failed:\n${r.stdout}\n${r.stderr}`);
    return r.stdout;
  };
  manage("migrate", "--noinput");
  manage("seed");
  const found = manage("shell", "-c", `from accounts.models import User; print("FOUND" if User.objects.filter(email="${SUPER_ADMIN.email}").exists() else "MISSING")`);
  if (!found.includes("FOUND")) manage("createsuperuser", "--noinput", "--email", SUPER_ADMIN.email, "--full_name", "E2E System Admin");

  const start = (cmd: string, args: string[], opts: { cwd: string; env: NodeJS.ProcessEnv }, log: string): ChildProcess => {
    const fd = fs.openSync(path.join(dir, log), "a");
    const child = spawn(cmd, args, { ...opts, stdio: ["ignore", fd, fd], windowsHide: true });
    if (child.pid) state.pids.push(child.pid);
    fs.writeFileSync(STATE_FILE, JSON.stringify(state));
    return child;
  };

  start(python, ["manage.py", "runserver", `127.0.0.1:${API_PORT}`, "--noreload"], { cwd: BACKEND_DIR, env: djangoEnv }, "django.log");

  // The production build lives apart from .next (a dev server may own that one). It is rebuilt when a source file is newer.
  const distDir = ".next-e2e";
  const webEnv: NodeJS.ProcessEnv = { ...process.env, NEXT_DIST_DIR: distDir, BACKEND_URL: API_URL, NODE_ENV: "production" };
  delete webEnv.NEXT_PUBLIC_API_URL;
  const nextBin = path.join(FRONTEND_DIR, "node_modules", "next", "dist", "bin", "next");
  const buildId = path.join(FRONTEND_DIR, distDir, "BUILD_ID");
  const sourceTime = Math.max(...["src", "public", "next.config.ts", "package.json"].map((p) => newestMtime(path.join(FRONTEND_DIR, p))));
  if (process.env.E2E_REBUILD === "1" || !fs.existsSync(buildId) || fs.statSync(buildId).mtimeMs < sourceTime) {
    console.log("e2e: building the production app (next build)...");
    const r = spawnSync(process.execPath, [nextBin, "build"], { cwd: FRONTEND_DIR, env: webEnv, encoding: "utf8" });
    if (r.status !== 0) throw new Error(`next build failed:\n${r.stdout}\n${r.stderr}`);
  }
  start(process.execPath, [nextBin, "start", "-p", String(WEB_PORT)], { cwd: FRONTEND_DIR, env: webEnv }, "next.log");

  await waitFor(`${API_URL}/api/v1/health/`, "Django");
  await waitFor(`${WEB_URL}/login`, "Next.js");
}
