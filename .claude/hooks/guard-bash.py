#!/usr/bin/env python3
"""PreToolUse hook for Bash: enforces the headset safety rules from CLAUDE.md.

- deny: things that must never happen (headset 207, force-stop of our agent,
  uninstall, factory reset, revoking debugging, printing private keys);
- ask: adb commands that change the headset state, so the user says "yes" first.

Input: JSON on stdin (tool_input.command). Deny = exit 2 + reason on stderr.
Ask = JSON on stdout with permissionDecision "ask".
"""

import json
import re
import sys

DENY = [
    (r"1WMHH868671295", "Headset 207 (1WMHH868671295) must never be touched. Use 203 (1WMHHA717K3282)."),
    (r"force-stop\s+com\.arena\.agent\b", "Never force-stop com.arena.agent: Android turns off its Accessibility service and the headset goes offline."),
    (r"\badb\b[^;&|]*\buninstall\b|\bpm\s+uninstall\b", "Never uninstall apps on a headset."),
    (r"pm\s+clear\s+com\.arena\.agent\b", "pm clear would delete the agent's ADB key and server token."),
    (r"FACTORY_RESET|MASTER_CLEAR|wipe-data|--wipe|\bwipe\s+data\b", "Never factory reset a headset."),
    (r"(>|\brm\b|\bmv\b|\bcp\b|\btee\b|sed\s+-i|\btruncate\b)[^;&|]*adb_keys",
     "Never change the trusted ADB key list on a headset (revokes debugging)."),
    (r"settings\s+put\s+global\s+adb_enabled\s+0", "Never turn off debugging on a headset."),
    (r"\b(cat|head|tail|less|more|base64|xxd|od|strings)\b[^|;&]*\b(adbkey(?!\.pub)|\S+\.pk8|\S+\.pem)\b",
     "Never print private keys."),
]

ASK_IF_ADB = [
    r"\breboot\b", r"\binstall\b", r"settings\s+(put|delete)\b", r"\bpm\s+(grant|revoke|disable|disable-user|enable|clear|install)\b",
    r"\bam\s+(start|start-activity|startservice|start-foreground-service|broadcast|force-stop|kill|kill-all)\b",
    r"\binput\s+(keyevent|tap|swipe|text)\b", r"\bmonkey\b", r"\bappops\s+set\b", r"\btcpip\b", r"\bsetprop\b",
    r"\bsvc\s", r"\bcmd\s+\w+", r"\brm\s", r"\bpush\b", r"\bkeygen\b",
]
ASK_ALWAYS = [r"provision\.sh", r"gradlew\b[^|;&]*\binstall\w*"]


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not cmd:
        return 0

    for pattern, reason in DENY:
        if re.search(pattern, cmd):
            print(f"Blocked by .claude/hooks/guard-bash.py: {reason}", file=sys.stderr)
            return 2

    uses_adb = re.search(r"(^|[\s/;&|(])adb\s", cmd) is not None
    if any(re.search(p, cmd) for p in ASK_ALWAYS) or (uses_adb and any(re.search(p, cmd) for p in ASK_IF_ADB)):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "This command changes the headset state. The user must say yes first.",
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
