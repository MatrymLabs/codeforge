#!/usr/bin/env bash
# One-command live deploy of CodeForge to Render as code.
#
# Prompts for your Render API key (kept OUT of shell history), auto-derives your
# workspace owner id from it, then runs `terraform apply` (which shows the plan
# and waits for your yes/no before creating anything). Free plan, a service
# distinct from the live demo. Run:  ./deploy.sh
#
# Tear down later with:  terraform destroy   (from this directory)
set -euo pipefail

cd "$(dirname "$0")"

command -v terraform >/dev/null || { echo "terraform not found on PATH. Install it, then re-run."; exit 1; }

# 1) API key, typed silently (never lands in ~/.bash_history or the process list).
read -rsp "Render API key (Account Settings -> API Keys): " RENDER_API_KEY
echo
export RENDER_API_KEY
[ -n "$RENDER_API_KEY" ] || { echo "No key entered. Aborting."; exit 1; }

# 2) Derive the workspace owner id from the key (no manual dashboard lookup).
RENDER_OWNER_ID="$(curl -fsS https://api.render.com/v1/owners \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['owner']['id'])")"
export RENDER_OWNER_ID
echo "Owner id: $RENDER_OWNER_ID"

# 3) Provision. `apply` previews the plan and asks before it creates the service.
terraform init -input=false
terraform apply
echo
echo "Live URL:"
terraform output -raw url
echo
