"""repoguard: guardrails and measurement for coding agents (lesson 5).

Reference implementations for the lesson 5 lab. The exercises in
labs/05-coding-agents/mine.py ask you to write your own versions of:

    bash_rules.check_bash        exercise 3
    hooks.check_path             exercise 4
    hooks.pre_tool_use           exercise 4
    hooks.post_tool_use          exercise 5
    injection.find_injections    exercise 7

Other modules are tools the lab uses as-is:

    shell        a small shell-command parser (pipelines, &&, ;, $(...), bash -c)
    instructions the CLAUDE.md / AGENTS.md linter (exercise 2)
    permissions  an approximate evaluator of Claude Code permission rules (exercise 6)
    skills       a SKILL.md checker (exercise 6)
    hookrunner   the stdin/stdout/exit-code wrapper that turns a function into a hook
    transcript   parser for `claude -p --output-format stream-json` transcripts
"""

__all__ = [
    "bash_rules",
    "hookrunner",
    "hooks",
    "injection",
    "instructions",
    "permissions",
    "shell",
    "skills",
    "transcript",
]
