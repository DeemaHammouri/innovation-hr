"""Scan the working tree and the whole git history for committed secrets. Exit code 1 if anything is found.

    python scripts/secret_scan.py

Looks for private keys, cloud and API tokens, hard-coded SECRET_KEY values and files that must never be committed (.env, databases,
uploads, key files). Placeholder passwords in docs and test fixtures are allowed through the ALLOW list below.
"""
import re
import subprocess
import sys

PATTERNS = {
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "aws key": r"AKIA[0-9A-Z]{16}",
    "api token": r"\b(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|xox[abp]-[A-Za-z0-9-]{10,})",
    "hard-coded secret key": r"""SECRET_KEY\s*=\s*['"][A-Za-z0-9!@#$%^&*()_+=-]{40,}['"]""",
}
FORBIDDEN_FILES = re.compile(r"(^|/)(\.env(\.[^/]*)?|[^/]*\.sqlite3|[^/]*\.pem|[^/]*\.key)$|(^|/)(private_media|media)/")
ALLOWED_FILES = re.compile(r"\.env\.example$")
ALLOW = ("dev-only-insecure-key-change-me",)  # the documented development default; production refuses it


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def main():
    found = []
    for name in set(git("ls-files").split("\n")) | set(git("log", "--all", "--name-only", "--format=").split("\n")):
        if name and FORBIDDEN_FILES.search(name) and not ALLOWED_FILES.search(name):
            found.append(f"forbidden file in repository or history: {name}")
    for label, rx in PATTERNS.items():
        for scope, out in (("history", git("log", "--all", "-p", "--format=%h", "-G" + rx)), ("tree", git("grep", "-nE", rx))):
            for line in out.split("\n"):
                if re.search(rx, line) and not any(a in line for a in ALLOW):
                    found.append(f"{label} ({scope}): {line[:120]}")
    for f in sorted(set(found)):
        print(f)
    print(f"{len(set(found))} finding(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
