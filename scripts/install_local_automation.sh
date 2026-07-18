#!/bin/zsh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_PATH="$HOME/Library/LaunchAgents/com.kbsmd.wnba-props-refresh.plist"
LOG_PATH="$REPO_DIR/data/manifests/automation.log"

mkdir -p "$REPO_DIR/data/manifests" "$HOME/Library/LaunchAgents"
sed \
  -e "s|__REPO_DIR__|$REPO_DIR|g" \
  -e "s|__LOG_PATH__|$LOG_PATH|g" \
  "$REPO_DIR/scripts/local-automation.plist.template" > "$PLIST_PATH"
launchctl bootout "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
echo "Installed daily WNBA props refresh at 8:00 PM: $PLIST_PATH"
