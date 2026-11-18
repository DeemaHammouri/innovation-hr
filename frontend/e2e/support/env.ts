import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export const API_PORT = 8100;
export const WEB_PORT = 3100;
export const API_URL = `http://127.0.0.1:${API_PORT}`;
export const WEB_URL = `http://localhost:${WEB_PORT}`;

export const FRONTEND_DIR = path.resolve(__dirname, "..", "..");
export const REPO_DIR = path.resolve(FRONTEND_DIR, "..");
export const BACKEND_DIR = path.join(REPO_DIR, "backend");
export const EVIDENCE_DIR = process.env.E2E_EVIDENCE_DIR ?? path.join(REPO_DIR, "docs", "evidence", "acceptance", "e2e");
export const STATE_FILE = path.join(os.tmpdir(), "innovation-e2e-state.json");

/** The Python that runs Django. Override with E2E_PYTHON; the default is the backend virtual environment. */
export function pythonPath(): string {
  if (process.env.E2E_PYTHON) return process.env.E2E_PYTHON;
  const candidates = [path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe"), path.join(BACKEND_DIR, ".venv", "bin", "python")];
  return candidates.find((c) => fs.existsSync(c)) ?? candidates[0];
}

export type E2eState = { dir: string; db: string; createdDir: boolean; pids: number[]; python: string };

export function readState(): E2eState {
  return JSON.parse(fs.readFileSync(STATE_FILE, "utf8")) as E2eState;
}

/** Accounts the harness makes. Every other account is made by the setup journey, through the screens. */
export const SUPER_ADMIN = { email: "e2e-super@e2e.test", password: "E2e-Super-Pass-2026!" };
export const CEO = { email: "e2e-ceo@e2e.test", password: "E2e-Ceo-Pass-2026!" };
export const STRONG_PASSWORD = "E2e-Strong-Pass-2026!";
