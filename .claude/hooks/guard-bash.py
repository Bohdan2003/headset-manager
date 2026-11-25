#!/usr/bin/env python3
"""PreToolUse hook for Bash: enforces the headset safety rules from CLAUDE.md.

- deny: things that must never happen (headset 207, force-stop of our agent,
  uninstall, factory reset, revoking debugging, printing private keys);
- deny for subagents: any adb or headset command;
- ask: adb commands, and calls to our server, that change the headset state, so the user says "yes" first.

Input: JSON on stdin (tool_input.command). Deny = exit 2 + reason on stderr.
Ask = JSON on stdout with permissionDecision "ask".
"""

import json
import re
import sys

DENY = [
    (r"1WMHH868671295", "Headset 207 (1WMHH868671295) must never be touched. Use 203 (1WMHHA717K3282)."),
    (r"(\bforce-stop\b|\b(am|activity)\s+(crash|stop-app|kill|stopservice|stop-service)\b)[^;&|]*\bcom\.arena\.agent\b", "Never stop com.arena.agent by hand: Android turns off its Accessibility service and the headset goes offline."),
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
    r"\bam\s+(start|start-activity|startservice|start-foreground-service|broadcast|force-stop|stop-app|crash|stopservice|stop-service|kill|kill-all)\b",
    r"\binput\s+(keyevent|tap|swipe|text)\b", r"\bmonkey\b", r"\bappops\s+set\b", r"\btcpip\b", r"\bsetprop\b",
    r"\bsvc\s", r"\bcmd\s+\w+", r"\brm\s", r"\bpush\b", r"\bkeygen\b",
    r"\bconnect\b",  # an address does not show which headset it is: it can be 207
]
ASK_ALWAYS = [
    r"provision\.sh", r"gradlew\b[^|;&]*\binstall\w*",
    # headset commands that go through our server
    r"\b(curl|wget|http|https|python3?|node)\b.*/api/(commands|setup)\b",
]
# adb, /path/adb, "adb", "$ADB", ${ADB}
USES_ADB = r"""(^|[\s/;&|(`"'])adb["'`]?(\s|$)|\$\{?ADB\b"""


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

    uses_adb = re.search(USES_ADB, cmd) is not None
    ask_always = any(re.search(p, cmd, re.DOTALL) for p in ASK_ALWAYS)

    # Claude Code sends agent_id only for subagents
    if data.get("agent_id") and (uses_adb or ask_always):
        print("Blocked by .claude/hooks/guard-bash.py: only the main session works with headsets. "
              "To search text about adb, use the Grep tool.", file=sys.stderr)
        return 2

    if ask_always or (uses_adb and any(re.search(p, cmd) for p in ASK_IF_ADB)):
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "This command can change a headset. Check that it is not 207. The user must say yes first.",
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
