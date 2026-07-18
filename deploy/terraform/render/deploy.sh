#!/usr/bin/env bash
# One-command live deploy of CodeForge to Render as code.
#
# Key sources (first that is set wins), so it works interactively or not:
#   1. RENDER_API_KEY already exported in the environment (non-interactive)
#   2. otherwise, prompt for it silently (kept OUT of shell history)
# Then it derives your workspace owner id and runs `terraform apply` (which
# previews the plan and waits for your yes/no). Free plan, a service distinct
# from the live demo. Run:  ./deploy.sh
#
# Tear down later with:  terraform destroy   (from this directory)
set -euo pipefail
cd "$(dirname "$0")"

command -v terraform >/dev/null || {
  echo "ERROR: terraform is not on your PATH. Install it (e.g. into ~/.local/bin) and re-run."
  exit 1
}

# 1) API key: reuse the env var if present, else prompt silently.
if [ -z "${RENDER_API_KEY:-}" ]; then
  read -rsp "Render API key (Render -> Account Settings -> API Keys): " RENDER_API_KEY
  echo
fi
export RENDER_API_KEY
[ -n "$RENDER_API_KEY" ] || { echo "ERROR: no API key provided."; exit 1; }

# 2) Derive the workspace owner id. Fail with a clear message (not a traceback)
#    if the key is rejected or the response is unexpected.
owners_json="$(curl -fsS https://api.render.com/v1/owners \
  -H "Authorization: Bearer $RENDER_API_KEY" 2>/dev/null || true)"
RENDER_OWNER_ID="$(printf '%s' "$owners_json" | python3 -c '
import sys, json
try:
    print(json.load(sys.stdin)[0]["owner"]["id"])
except Exception:
    pass' 2>/dev/null)"
if [ -z "$RENDER_OWNER_ID" ]; then
  echo "ERROR: could not authenticate to Render with that key (no owner returned)."
  echo "Check the key at Render -> Account Settings -> API Keys, then re-run."
  exit 1
fi
export RENDER_OWNER_ID
echo "Owner id: $RENDER_OWNER_ID"

# 3) Provision. `apply` previews the plan and asks before it creates anything.
terraform init -input=false
terraform apply
echo
echo "Live URL:"
terraform output -raw url
echo
