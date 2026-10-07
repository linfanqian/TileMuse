# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""PreToolUse hook: block git commits/pushes on or to main, and force-pushes.

Reads the Bash/PowerShell tool call from stdin. Prints a deny decision to
stdout when blocked; otherwise exits silently so normal permissions apply.
"""

import json
import re
import shlex
import subprocess
import sys

PROTECTED = "main"
SEPARATORS = re.compile(r"&&|\|\||[;|&\n]")
# git global options that take a separate value, e.g. `git -C dir commit`
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def current_branch(cwd: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def tokenize(segment: str) -> list[str]:
    try:
        return shlex.split(segment)
    except ValueError:
        return segment.split()


def git_subcommand(tokens: list[str]) -> tuple[str, list[str]] | None:
    """Return (subcommand, args) if the tokens are a git invocation."""
    if not tokens or tokens[0].lower() not in ("git", "git.exe"):
        return None
    i = 1
    while i < len(tokens) and tokens[i].startswith("-"):
        i += 2 if tokens[i] in GIT_OPTS_WITH_VALUE else 1
    if i >= len(tokens):
        return None
    return tokens[i], tokens[i + 1:]


def is_force(args: list[str]) -> bool:
    for a in args:
        if a.startswith("--force") or a == "--mirror":
            return True
        if re.fullmatch(r"-[a-zA-Z]*f[a-zA-Z]*", a):
            return True
        if a.startswith("+"):
            return True
    return False


def pushes_to_main(args: list[str], branch: str | None) -> bool:
    positional = [a for a in args if not a.startswith("-")]
    if "--all" in args:
        return True
    refspecs = positional[1:]  # positional[0] is the remote
    if not refspecs:
        return branch == PROTECTED
    for ref in refspecs:
        dest = ref.split(":")[-1].removeprefix("refs/heads/")
        if dest == PROTECTED or (dest == "HEAD" and branch == PROTECTED):
            return True
    return False


def main() -> None:
    data = json.load(sys.stdin)
    command = data.get("tool_input", {}).get("command", "")
    if "git" not in command:
        return
    branch = current_branch(data.get("cwd") or ".")

    for segment in SEPARATORS.split(command):
        parsed = git_subcommand(tokenize(segment.strip()))
        if not parsed:
            continue
        sub, args = parsed
        # Track branch switches earlier in the same compound command.
        if sub in ("switch", "checkout") and "--" not in args:
            names = [a for a in args if not a.startswith("-")]
            if names:
                branch = names[0]
        elif sub == "commit" and branch == PROTECTED:
            deny(f"Committing on '{PROTECTED}' is not allowed. Create a branch "
                 "<type>/<person>-<issue#>-<short-name> and commit there.")
        elif sub == "push":
            if is_force(args):
                deny("Force-pushing is not allowed in this repo.")
            if pushes_to_main(args, branch):
                deny(f"Pushing to '{PROTECTED}' is not allowed. Push your "
                     "feature branch and open a PR instead.")


if __name__ == "__main__":
    main()
