---
type: llm
weight: 0.001
---

PASS if the final message tells the user that the existing duplicate implementations were not all equivalent, i.e. at least one of these behaviour differences between copies is named: the month in formatTime (utils/format.ts) lacks the +1, formatTime/ProfilePage do not zero-pad, or the server report's toDay takes the UTC date via toISOString while the others use local time.
FAIL if the message only says the duplicates were replaced and never mentions that the copies behaved differently.
