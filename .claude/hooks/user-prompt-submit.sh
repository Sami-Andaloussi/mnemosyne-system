#!/usr/bin/env bash
# Non-blocking prompt hook. It extracts the prompt field when possible and falls back safely to the
# complete payload when extraction fails.
set -u

payload=$(cat)

# Extract just the operator's prompt; fall back to the raw payload if python3 is unavailable/fails.
prompt=$(printf '%s' "$payload" | python3 -c 'import sys, json
try:
    sys.stdout.write(json.load(sys.stdin).get("prompt", ""))
except Exception:
    pass' 2>/dev/null) || prompt=""
haystack="${prompt:-$payload}"

if printf '%s' "$haystack" | grep -iqE \
  'mosyne|ingère|ingérer|ingere|ingerer|ingest|mémorise|memorise|morise|(^|[^a-zA-Z])(garde|range|ranger|retiens)[ -](ça|ca|ceci|cela|moi)|(^|[^a-zA-Z])(à |a )ranger|(^|[^a-zA-Z])(ajoute|mets|classe|range|ranger|garde)[^.]{0,25}(corpus|biblioth|knowledge|mémoire|memoire|distilled|étagère|etagere)'
then
  echo "[Mnemosyne - PUSH reminder] You signaled an addition to the system. Do NOT defer it:"
  echo "classify it (raw/<domain>, distilled, memory, or project), ingest it via the right"
  echo "capability under the Guard, right away. Delegate the volume to a smaller model/agent"
  echo "if needed. See README.md and ARCHITECTURE.md for the public project guide."
fi

# Retrieve candidate lessons without blocking the host workflow.
racine=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
printf '%s' "$payload" | env \
  PYTHONPATH="$racine/system/lib" \
  CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$racine}" \
  python3 -m mnemosyne.runtime.lecons_amorce 2>/dev/null || true

exit 0
