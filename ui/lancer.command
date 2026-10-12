#!/bin/zsh

set -u
cd "${0:A:h}" || exit 1

JOURNAL=".journal/serveur.log"

arreter() {
  local pids cmd ou reste
  pids="$(pgrep -f 'serve\.py' 2>/dev/null || true)"
  [[ -z "$pids" ]] && return 0

  for pid in ${=pids}; do
    cmd="$(ps -o command= -p "$pid" 2>/dev/null)"
    [[ "$cmd" == *serve.py* ]] || continue
    ou="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p')"
    print "  stopping the server already running -- PID $pid${ou:+  ($ou)}"
    kill "$pid" 2>/dev/null
  done

  for _ in {1..30}; do
    pgrep -f 'serve\.py' >/dev/null 2>&1 || return 0
    sleep 0.1
  done
  reste="$(pgrep -f 'serve\.py' 2>/dev/null || true)"
  [[ -n "$reste" ]] && kill -9 ${=reste} 2>/dev/null
  return 0
}

if [[ "${1:-}" == "stop" ]]; then
  arreter
  print "\n  Dashboard stopped.\n"
  exit 0
fi

arreter

mkdir -p .journal
[[ -f "$JOURNAL" ]] && mv -f "$JOURNAL" "${JOURNAL%.log}.precedent.log"
: > "$JOURNAL"

nohup python3 -u serve.py --sans-navigateur >>"$JOURNAL" 2>&1 &
serveur=$!
disown 2>/dev/null

url=""
for _ in {1..100}; do
  url="$(grep -o 'http://127\.0\.0\.1:[0-9]*/' "$JOURNAL" 2>/dev/null | tail -1)"
  [[ -n "$url" ]] && break
  kill -0 "$serveur" 2>/dev/null || break
  sleep 0.1
done

if [[ -z "$url" ]]; then
  arreter
  print "\n  The server did not start. What it said:\n"
  cat "$JOURNAL"
  print ""
  exit 1
fi

deja="$(osascript - "$url" 2>/dev/null <<'APPLESCRIPT'
on run argv
  set cible to item 1 of argv
  tell application "Safari"
    if it is not running then return "absent"
    repeat with f in windows
      repeat with o in tabs of f
        if URL of o is cible then
          set URL of o to cible   -- reload: the tab may date from a dead server
          set current tab of f to o
          activate
          return "trouve"
        end if
      end repeat
    end repeat
  end tell
  return "absent"
end run
APPLESCRIPT
)"

[[ "$deja" == "trouve" ]] || open "$url"

print "\n  Mnémosyne - dashboard"
print "  $url"
print "\n  It runs in the background: you can close this terminal."
print "  To stop it:  ui stop\n"
