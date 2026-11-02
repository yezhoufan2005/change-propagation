import json, sys, os
d = json.load(sys.stdin)
ti = d.get("tool_input", {})
fp = ti.get("file_path", "")
if not fp.endswith((".vue", ".ts", ".tsx", ".js", ".go", ".py")):
    sys.exit(0)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ""}}))
