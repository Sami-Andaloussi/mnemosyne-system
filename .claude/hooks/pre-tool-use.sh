#!/usr/bin/env bash
# THE SHELL GUARD.
#
# THE ONLY GATE IN THIS REPO THAT BLOCKS A GESTURE. The other hooks PRINT; this one REFUSES (exit
# code 2) when a Bash command contains a backtick the shell would SUBSTITUTE. A lesson without a
# barrier is just a wish - this hook is that barrier, not another paragraph of doctrine to reread.
#
# FAIL-OPEN EVERYWHERE ELSE, ON PURPOSE: python missing, module broken, unreadable JSON -> let it
# through. A guard that breaks the ability to run commands at all gets removed within the hour. It is
# better to miss a bite than to block an innocent command.
racine=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
charge=$(cat)
sortie=$(printf '%s' "$charge" | env \
  PYTHONPATH="$racine/system/lib" \
  python3 -m mnemosyne.runtime.garde_shell_run 2>&1)
rc=$?
if [ "$rc" -eq 2 ]; then
  printf '%s\n' "$sortie" >&2
  exit 2
fi
exit 0
