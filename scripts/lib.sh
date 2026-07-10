#!/usr/bin/env bash
# CARD: ritual-lib -- shared shell helpers for the Ritual ceremonies.
#
# Sourced by scripts/ritual.sh, scripts/ritual_down.sh, and scripts/ritual_fast.sh so
# the palette and the voice live in exactly one place. Extracting this removed three
# copies of the same colour block and message functions -- change the look here, once.
#
# Provides: BOLD DIM GREEN RED YELLOW CYAN OFF · spark_line/step · ok · warn · die.

# --- A little light (colour only when writing to a real terminal) ----------
if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; RED=$'\033[31m'
  YELLOW=$'\033[33m'; CYAN=$'\033[36m'; OFF=$'\033[0m'
else
  BOLD=""; DIM=""; GREEN=""; RED=""; YELLOW=""; CYAN=""; OFF=""
fi

spark_line() { printf '%b⚒  %s%b\n' "$CYAN" "$1" "$OFF"; }
step()       { spark_line "$1"; }              # the shutdown ceremony's name for the same line
ok()         { printf '%b   ✓ %s%b\n' "$GREEN"  "$1" "$OFF"; }
warn()       { printf '%b   ! %s%b\n' "$YELLOW" "$1" "$OFF"; }
die()        { printf '%b   ✗ %s%b\n' "$RED"    "$1" "$OFF"; exit 1; }
