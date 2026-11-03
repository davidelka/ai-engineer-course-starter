"""A small Dockerfile parser and the lesson 27 lint rules (reference implementation).

Pure Python, no Docker needed. The parser understands what the lab Dockerfiles use:
comments and parser directives, line continuations (\\ or the `# escape=` char),
heredocs (RUN <<EOF ... EOF), JSON (exec) form, and multi-stage builds.

    instrs = parse_dockerfile(Path("Dockerfile").read_text())
    findings = lint_dockerfile(text, dockerignore_text=Path("Dockerfile.dockerignore").read_text())

Real linters you should know: `docker build --check` (BuildKit's built-in checks) and
hadolint. This module exists so you can see, and write, the rules yourself.
"""

from __future__ import annotations

import fnmatch
import json
import re
import shlex
from dataclasses import dataclass, field
from typing import Optional

from .findings import Finding


# ------------------------------------------------------------------ parsing
@dataclass
class Instruction:
    line: int  # 1-based line where the instruction starts
    cmd: str  # upper-case keyword: FROM, RUN, COPY, ENV, USER, ...
    args: str  # everything after the keyword, continuations joined with a space
    stage: int  # index of the build stage (0 for the first FROM; -1 before any FROM)
    flags: dict = field(default_factory=dict)  # leading --flags, e.g. {"from": "builder", "chown": "app"}
    heredoc: str = ""  # body of a heredoc, when the instruction has one

    @property
    def rest(self) -> str:
        """args without the leading --flags."""
        return _strip_flags(self.args)[1]

    @property
    def is_exec_form(self) -> bool:
        """True for the JSON form: CMD ["uvicorn", "app:app"]."""
        r = self.rest.strip()
        if not r.startswith("["):
            return False
        try:
            return isinstance(json.loads(r), list)
        except json.JSONDecodeError:
            return False


@dataclass
class Stage:
    index: int
    base: str  # the image or stage name after FROM
    alias: Optional[str]  # the name after AS
    line: int
    instructions: list  # instructions of this stage, FROM included


_FLAG = re.compile(r"^--([a-zA-Z][\w-]*)(?:=(\S*))?\s*")
_HEREDOC = re.compile(r"<<(-?)(['\"]?)([A-Za-z_][\w]*)\2")


def _strip_flags(args: str) -> tuple[dict, str]:
    flags, rest = {}, args.lstrip()
    while True:
        m = _FLAG.match(rest)
        if not m:
            return flags, rest
        flags[m.group(1).lower()] = m.group(2) if m.group(2) is not None else True
        rest = rest[m.end():]


def parse_dockerfile(text: str) -> list[Instruction]:
    lines = text.splitlines()
    escape = "\\"
    # parser directives: only at the very top, as "# key=value" comments
    for raw in lines:
        m = re.match(r"^\s*#\s*(\w+)\s*=\s*(\S+)\s*$", raw)
        if not m:
            break
        if m.group(1).lower() == "escape" and m.group(2) in ("\\", "`"):
            escape = m.group(2)
    out: list[Instruction] = []
    stage = -1
    i = 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        if not s or s.startswith("#"):
            i += 1
            continue
        start = i + 1
        parts = []
        while True:
            cur = lines[i].rstrip()
            if cur.endswith(escape):
                parts.append(cur[:-1].strip())
                i += 1
                # comment lines and blank lines inside a continuation are skipped
                while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith("#")):
                    i += 1
                if i >= len(lines):
                    break
                continue
            parts.append(cur.strip())
            i += 1
            break
        logical = " ".join(p for p in parts if p)
        kw, _, args = logical.partition(" ")
        kw = kw.upper()
        heredoc = ""
        m = _HEREDOC.search(args) if kw in ("RUN", "COPY") else None
        if m:
            term, body = m.group(3), []
            while i < len(lines):
                line = lines[i]
                i += 1
                if (line.strip() if m.group(1) else line) == term:
                    break
                body.append(line)
            heredoc = "\n".join(body)
        if kw == "FROM":
            stage += 1
        flags, _ = _strip_flags(args)
        out.append(Instruction(line=start, cmd=kw, args=args.strip(), stage=stage, flags=flags, heredoc=heredoc))
    return out


def from_parts(instr: Instruction) -> tuple[str, Optional[str]]:
    """FROM [--platform=..] image [AS name] -> (image, name)."""
    toks = instr.rest.split()
    image = toks[0] if toks else ""
    alias = toks[2] if len(toks) >= 3 and toks[1].lower() == "as" else None
    return image, alias


def stages(instrs: list[Instruction]) -> list[Stage]:
    out: list[Stage] = []
    for ins in instrs:
        if ins.cmd == "FROM":
            image, alias = from_parts(ins)
            out.append(Stage(ins.stage, image, alias, ins.line, [ins]))
        elif out:
            out[-1].instructions.append(ins)
    return out


def stage_names(instrs: list[Instruction]) -> set[str]:
    """Names that refer to earlier stages: aliases and indexes ("0", "1", ...)."""
    names = set()
    for st in stages(instrs):
        names.add(str(st.index))
        if st.alias:
            names.add(st.alias.lower())
    return names


def split_image_ref(ref: str) -> tuple[str, Optional[str], Optional[str]]:
    """'ghcr.io/astral-sh/uv:0.13.6@sha256:ab..' -> ('ghcr.io/astral-sh/uv', '0.13.6', 'sha256:ab..').
    A ':' before the last '/' is a registry port, not a tag."""
    digest = None
    if "@" in ref:
        ref, digest = ref.split("@", 1)
    name, tag = ref, None
    last = ref.rsplit("/", 1)[-1]
    if ":" in last:
        name, tag = ref.rsplit(":", 1)
    return name, tag, digest


def env_pairs(instr: Instruction) -> list[tuple[str, str]]:
    """ENV/ARG/LABEL key-value pairs.
    ENV A=1 B="two words"  -> [("A","1"), ("B","two words")]
    ENV A some value        -> [("A","some value")]      (legacy form, ENV only)
    ARG NAME                -> [("NAME", "")]"""
    rest = instr.rest.strip()
    if not rest:
        return []
    first = rest.split(None, 1)[0]
    if instr.cmd in ("ENV",) and "=" not in first:
        key, _, value = rest.partition(" ")
        return [(key, value.strip().strip('"').strip("'"))]
    try:
        toks = shlex.split(rest, posix=True)
    except ValueError:
        toks = rest.split()
    pairs = []
    for t in toks:
        k, eq, v = t.partition("=")
        pairs.append((k, v if eq else ""))
    return pairs


# ------------------------------------------------------------------ secret detection
# Name-based detection always has false positives and negatives: "token(?!s)" keeps
# MAX_TOKENS (a number, not a secret) out, while ACCESS_TOKEN and HF_TOKEN are caught.
SECRET_NAME = re.compile(
    r"(api[_-]?key|secret|token(?!s)|passw(or)?d|passwd|credential|private[_-]?key|access[_-]?key|(^|_)key$)", re.I)
# names that point AT a secret instead of holding one
POINTER_SUFFIX = re.compile(r"(_FILE|_PATH|_ARN|_URL|_NAME|_ID_FILE)$", re.I)
SECRET_VALUE = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{8,}|sk-proj-[A-Za-z0-9_-]{8,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
    r"|ghp_[A-Za-z0-9]{20,}|xox[bpa]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{20,})")


def looks_like_secret_name(name: str) -> bool:
    return bool(SECRET_NAME.search(name)) and not POINTER_SUFFIX.search(name)


def looks_like_secret_value(value: str) -> bool:
    return bool(SECRET_VALUE.search(value or ""))


# ------------------------------------------------------------------ the rules
ROOT_USERS = {"root", "0"}


def rule_base_image_pinned(instrs: list[Instruction]) -> list[Finding]:
    """Every external image (FROM, COPY --from=<image>) has an explicit tag that is not
    'latest'. Pinned by tag only -> info (add a digest for reproducible builds)."""
    out: list[Finding] = []
    known: set[str] = set()
    for ins in instrs:
        ref = None
        if ins.cmd == "FROM":
            ref, alias = from_parts(ins)
        elif ins.cmd == "COPY" and isinstance(ins.flags.get("from"), str):
            ref = ins.flags["from"]
        if ref is None:
            continue
        if ref.lower() in known or ref.lower() == "scratch":
            pass
        elif "$" in ref:
            out.append(Finding("base_image_pinned", "warning", str(ins.line),
                               f"image {ref!r} comes from a build arg: make sure its default is pinned"))
        else:
            name, tag, digest = split_image_ref(ref)
            if digest:
                pass
            elif tag is None:
                out.append(Finding("base_image_pinned", "error", str(ins.line),
                                   f"image {ref!r} has no tag, which means :latest: pin a version"))
            elif tag.lower() == "latest":
                out.append(Finding("base_image_pinned", "error", str(ins.line),
                                   f"image {ref!r} uses :latest: pin a version"))
            else:
                out.append(Finding("base_image_pinned", "info", str(ins.line),
                                   f"image {ref!r} is pinned by tag only; add @sha256:... for reproducible builds"))
        if ins.cmd == "FROM":
            known.add(str(ins.stage))
            if alias:
                known.add(alias.lower())
    return out


def _effective_user(st: Stage, by_name: dict) -> tuple[str, int]:
    """(user, line) in force at the end of a stage. Stages built FROM an earlier stage
    inherit its user; external images are assumed to run as root unless the tag says
    'nonroot' (distroless images do)."""
    user, line = None, st.line
    for ins in st.instructions:
        if ins.cmd == "USER":
            user, line = ins.rest.strip().split(":")[0], ins.line
    if user is not None:
        return user, line
    parent = by_name.get(st.base.lower())
    if parent is not None and parent.index < st.index:
        return _effective_user(parent, by_name)[0], st.line
    return ("nonroot" if "nonroot" in st.base.lower() else "root"), st.line


def rule_runs_as_non_root(instrs: list[Instruction]) -> list[Finding]:
    """The FINAL stage (what `docker build` produces by default) must not run as root."""
    sts = stages(instrs)
    if not sts:
        return [Finding("runs_as_non_root", "error", "1", "no FROM instruction")]
    by_name = {}
    for st in sts:
        by_name[str(st.index)] = st
        if st.alias:
            by_name[st.alias.lower()] = st
    final = sts[-1]
    user, line = _effective_user(final, by_name)
    if user.lower() in ROOT_USERS:
        how = "USER root" if any(i.cmd == "USER" for i in final.instructions) else "no USER instruction"
        return [Finding("runs_as_non_root", "error", str(line),
                        f"final stage runs as root ({how}): add a system user and switch with USER")]
    return []


def rule_no_secrets_in_build(instrs: list[Instruction]) -> list[Finding]:
    """No secrets in ENV/ARG, and no key-shaped literals anywhere in the Dockerfile.

    - ENV with a secret-like name and a non-empty value          -> error
    - ARG with a secret-like name (with or without a default)    -> error
      (build args end up in the image history; use RUN --mount=type=secret)
    - a value that looks like a real key (sk-ant-..., AKIA...) in any instruction -> error
    Names ending in _FILE, _PATH, _ARN, _URL, _NAME point at a secret and are fine."""
    out: list[Finding] = []
    for ins in instrs:
        flagged_value = False
        if ins.cmd in ("ENV", "ARG"):
            for key, value in env_pairs(ins):
                if looks_like_secret_value(value):
                    out.append(Finding("no_secrets_in_build", "error", str(ins.line),
                                       f"{ins.cmd} {key} holds a value that looks like a real key"))
                    flagged_value = True
                elif looks_like_secret_name(key) and (ins.cmd == "ARG" or value):
                    hint = ("build args are recorded in the image history: use RUN --mount=type=secret"
                            if ins.cmd == "ARG" else "it is baked into every layer: inject it at run time")
                    out.append(Finding("no_secrets_in_build", "error", str(ins.line),
                                       f"{ins.cmd} {key} looks like a secret; {hint}"))
        if not flagged_value and looks_like_secret_value(ins.args + "\n" + ins.heredoc):
            out.append(Finding("no_secrets_in_build", "error", str(ins.line),
                               f"{ins.cmd} contains a literal that looks like a real key"))
    return out


def rule_healthcheck(instrs: list[Instruction]) -> list[Finding]:
    sts = stages(instrs)
    if not sts:
        return []
    final = sts[-1]
    hc = [i for i in final.instructions if i.cmd == "HEALTHCHECK"]
    if not hc:
        return [Finding("healthcheck", "warning", str(final.line),
                        "final stage has no HEALTHCHECK (docker and compose use it; ECS needs its own healthCheck too)")]
    if hc[-1].rest.strip().upper() == "NONE":
        return [Finding("healthcheck", "warning", str(hc[-1].line), "HEALTHCHECK NONE disables health checks")]
    return []


def rule_exec_form(instrs: list[Instruction]) -> list[Finding]:
    out = []
    for ins in instrs:
        if ins.cmd in ("CMD", "ENTRYPOINT") and ins.stage == max(i.stage for i in instrs) and not ins.is_exec_form:
            out.append(Finding("exec_form", "warning", str(ins.line),
                               f"{ins.cmd} in shell form: /bin/sh becomes PID 1 and does not forward SIGTERM; "
                               "use the JSON form [\"...\"]"))
    return out


def rule_lean_layers(instrs: list[Instruction]) -> list[Finding]:
    out = []
    for ins in instrs:
        if ins.cmd != "RUN":
            continue
        body = ins.args + " " + ins.heredoc
        cache_mount = "type=cache" in str(ins.flags.get("mount", ""))
        if re.search(r"\bpip3?\s+install\b", body) and "--no-cache-dir" not in body and not cache_mount:
            out.append(Finding("lean_layers", "warning", str(ins.line),
                               "pip install without --no-cache-dir (or a cache mount) keeps the wheel cache in the layer"))
        if re.search(r"apt-get\s+install", body) and "rm -rf /var/lib/apt/lists" not in body and not cache_mount:
            out.append(Finding("lean_layers", "warning", str(ins.line),
                               "apt-get install without removing /var/lib/apt/lists in the same RUN"))
    return out


def rule_add_vs_copy(instrs: list[Instruction]) -> list[Finding]:
    out = []
    for ins in instrs:
        if ins.cmd == "ADD":
            src = ins.rest.split()[0] if ins.rest.split() else ""
            if not re.search(r"\.(tar|tgz|tar\.gz|tar\.xz)$", src):
                out.append(Finding("add_vs_copy", "warning", str(ins.line),
                                   "use COPY for local files; ADD also fetches URLs and unpacks archives"))
    return out


# ------------------------------------------------------------------ .dockerignore
def _ignored(path: str, patterns: list[str]) -> bool:
    """Docker semantics, simplified: the LAST matching pattern wins; '!' re-includes."""
    result = False
    for p in patterns:
        neg = p.startswith("!")
        pat = p[1:] if neg else p
        pat = pat.strip("/")
        candidates = {pat}
        if pat.startswith("**/"):
            candidates.add(pat[3:])
        if any(fnmatch.fnmatchcase(path, c) for c in candidates) or \
                any(fnmatch.fnmatchcase(path.split("/")[0], c) for c in candidates):
            result = not neg
    return result


def dockerignore_patterns(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip() and not line.strip().startswith("#")]


def rule_dockerignore(instrs: list[Instruction], dockerignore_text: Optional[str]) -> list[Finding]:
    """A build that copies whole directories needs an ignore file that keeps .env,
    .git and the venv out of the build context."""
    copies_dirs = [i for i in instrs if i.cmd in ("COPY", "ADD") and "from" not in i.flags
                   and any(t in (".", "./") or t.endswith("/") for t in i.rest.split()[:-1])]
    if dockerignore_text is None:
        if copies_dirs:
            return [Finding("dockerignore", "error", str(copies_dirs[0].line),
                            "copies a directory but there is no .dockerignore: .env, .git and .venv go into the build context")]
        return [Finding("dockerignore", "warning", "1", "no .dockerignore next to the Dockerfile")]
    pats = dockerignore_patterns(dockerignore_text)
    out = []
    if not _ignored(".env", pats):
        out.append(Finding("dockerignore", "error", "1", ".dockerignore does not exclude .env"))
    # .env files inside re-included directories (an allowlist: "*" then "!llmkit/") or any subdirectory
    dirs = [p[1:].strip("/").rstrip("*").rstrip("/") for p in pats if p.startswith("!")]
    leaks = [d for d in (dirs or ["some/sub/dir"]) if d and not _ignored(f"{d}/.env", pats)]
    if leaks:
        where = f"inside {leaks[0]}/" if dirs else "in subdirectories"
        out.append(Finding("dockerignore", "error", "1",
                           f".env files {where} are not excluded: add **/.env as the LAST line (the last match wins)"))
    for path in (".git", ".venv"):
        if not _ignored(path, pats):
            out.append(Finding("dockerignore", "warning", "1", f".dockerignore does not exclude {path}"))
    return out


RULES = [rule_base_image_pinned, rule_runs_as_non_root, rule_no_secrets_in_build, rule_healthcheck,
         rule_exec_form, rule_lean_layers, rule_add_vs_copy]


def lint_dockerfile(text: str, dockerignore_text: Optional[str] = None, *, check_ignore: bool = True,
                    rules: Optional[dict] = None) -> list[Finding]:
    """Run all rules. `rules` can replace some by name (the lab passes your versions)."""
    instrs = parse_dockerfile(text)
    out: list[Finding] = []
    for rule in RULES:
        fn = (rules or {}).get(rule.__name__, rule)
        out.extend(fn(instrs))
    if check_ignore:
        out.extend(rule_dockerignore(instrs, dockerignore_text))
    return out
