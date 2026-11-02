#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/../../tools/workspace.sh"
# Real history up to 182132e3, the parent of the upstream fix 6148ea97 (both copies fixed there).
setup_history_repo thingspanel-frontend-community case/action-placeholder master
setup_repo thingspanel-backend-community
