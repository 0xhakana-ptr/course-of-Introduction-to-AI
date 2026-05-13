$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path "$PSScriptRoot\..\..")

uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests/tools/test_workspace_tools.py backend/tests/acceptance/test_agent_loop_acceptance.py -q
