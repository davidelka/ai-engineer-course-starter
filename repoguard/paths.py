"""Which paths are secrets, and which paths an agent must not change.

Shared by the Bash rules (exercise 3) and the file-path checks (exercise 4).
"""

from __future__ import annotations

import posixpath

ENV_TEMPLATES = {".env.example", ".env.sample", ".env.template"}
KEY_NAMES = {"id_rsa", "id_ed25519", "id_ecdsa", "id_dsa", ".netrc", ".pgpass", ".npmrc", ".pypirc"}
KEY_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


def _clean(path: str) -> str:
    p = path.strip().strip("'\"")
    if p.startswith("@"):  # curl -d @file
        p = p[1:]
    if "=@" in p:  # curl -F name=@file
        p = p.split("=@", 1)[1]
    return posixpath.normpath(p.replace("\\", "/")) if p else ""


def secret_reason(path: str) -> str | None:
    """Return why `path` is a secret file, or None. Works on relative and absolute paths.

    Secrets: `.env` and `.env.<anything>` except the templates .env.example / .env.sample /
    .env.template; anything inside a directory named `secrets`; private keys and credential
    files (id_rsa, id_ed25519, *.pem, *.key, .netrc, .pgpass, .npmrc, .pypirc); anything
    under `.ssh/`; `.aws/credentials`.
    """
    p = _clean(path)
    if not p or p == ".":
        return None
    parts = [x for x in p.split("/") if x]
    if not parts:
        return None
    name = parts[-1]
    if name == ".env" or (name.startswith(".env.") and name not in ENV_TEMPLATES):
        return f"{name} holds secrets (environment file)"
    if "secrets" in parts[:-1] or name == "secrets":
        return f"{p} is inside a secrets directory"
    if name in KEY_NAMES or name.endswith(KEY_SUFFIXES):
        return f"{name} looks like a private key or credentials file"
    if ".ssh" in parts:
        return f"{p} is inside .ssh"
    if len(parts) >= 2 and parts[-2] == ".aws" and name in ("credentials", "config"):
        return f"{p} holds cloud credentials"
    return None


def protected_write_reason(rel: str) -> str | None:
    """Why an agent must not write `rel` (a normalized path relative to the project), or None.

    Protected for writing (reading is fine): anything inside .git/, the agent's own
    guardrails (.claude/settings.json and anything under .claude/hooks/), and lock files
    (uv.lock, poetry.lock, package-lock.json), which only the package manager should write.
    """
    parts = [x for x in rel.split("/") if x]
    if not parts:
        return None
    if parts[0] == ".git":
        return "files inside .git/ are managed by git"
    if parts[0] == ".claude" and (rel == ".claude/settings.json" or (len(parts) > 1 and parts[1] == "hooks")):
        return f"{rel} configures the agent's own guardrails; a human changes it"
    if parts[-1] in ("uv.lock", "poetry.lock", "package-lock.json"):
        return f"{parts[-1]} is written by the package manager, not by hand"
    return None
