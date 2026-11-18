import { spawnSync } from "node:child_process";
import fs from "node:fs";
import { STATE_FILE, readState } from "./support/env";

export default async function globalTeardown() {
  if (!fs.existsSync(STATE_FILE)) return;
  const state = readState();
  for (const pid of state.pids) {
    if (process.platform === "win32") spawnSync("taskkill", ["/pid", String(pid), "/T", "/F"], { stdio: "ignore" });
    else {
      try {
        process.kill(pid, "SIGKILL");
      } catch {
        /* already gone */
      }
    }
  }
  await new Promise((r) => setTimeout(r, 800));
  if (state.createdDir) fs.rmSync(state.dir, { recursive: true, force: true });
  fs.rmSync(STATE_FILE, { force: true });
}
