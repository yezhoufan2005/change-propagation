---
type: llm
weight: 0.001
---

PASS if the final message tells the user that the two actionValueChange copies were not equivalent: scene-edit/index.vue validates four action_param_type values (command, c_attribute, c_telemetry, c_command) while linkage-edit/modules/edit-action.vue validates only command, and says how the shared function handles that.
FAIL if the message never points out this difference.
