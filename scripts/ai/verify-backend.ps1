$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path "$PSScriptRoot\..\..")

uv run --python 3.11 --with-requirements backend/requirements.txt pytest backend/tests -q
