#!/bin/sh
# Crypto installer only: identify the d-i session by its tty-style name,
# excluding independently named service sessions. Refuse ambiguity.
set -eu
sessions=$(screen -ls root/ 2>/dev/null | awk '$1 ~ /^[0-9]+\.tty[^ ]+$/ {print $1}')
set -- $sessions
[ "$#" = 1 ] || { echo 'Cannot identify a unique installer tty Screen session.' >&2; exit 1; }
session=$1
if [ "${1-}" = --unused ]; then exit 1; fi
case "${SCREEN_QUERY_ONLY:-0}" in 1) printf '%s\n' "$session";; *) exec screen -x "root/$session" -p "${INSTALLER_WINDOW:-1}";; esac
