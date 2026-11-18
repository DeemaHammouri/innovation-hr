import { spawnSync } from "node:child_process";
import path from "node:path";
import { BACKEND_DIR, CEO, SUPER_ADMIN, readState } from "./env";

/** Runs a manage.py command against the suite's throwaway database (never backend/db.sqlite3). */
export function manage(...args: string[]): string {
  const state = readState();
  const r = spawnSync(state.python, ["manage.py", ...args], {
    cwd: BACKEND_DIR,
    encoding: "utf8",
    env: {
      ...process.env,
      DJANGO_DB_PATH: state.db,
      PRIVATE_MEDIA_ROOT: path.join(state.dir, "private_media"),
      DJANGO_SUPERUSER_PASSWORD: SUPER_ADMIN.password,
      CEO_EMAIL: CEO.email,
      CEO_PASSWORD: CEO.password,
      PYTHONIOENCODING: "utf-8",
      PYTHONUTF8: "1",
    },
  });
  if (r.status !== 0) throw new Error(`manage.py ${args.join(" ")} failed:\n${r.stdout}\n${r.stderr}`);
  return r.stdout;
}
