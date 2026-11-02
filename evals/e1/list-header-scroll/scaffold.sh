#!/usr/bin/env bash
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/../../tools/workspace.sh"
setup_repo thingspanel-frontend-community "$(dirname "${BASH_SOURCE[0]}")/plant"
setup_repo thingspanel-backend-community
