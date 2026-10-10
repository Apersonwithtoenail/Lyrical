#!/usr/bin/env bash
# uninstall.sh — remove Lyrical
set -e

APP_ID="lyrical"
rm -f "$HOME/.local/bin/$APP_ID"
rm -f "$HOME/.local/share/applications/$APP_ID.desktop"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/$APP_ID.svg"

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "✅ Lyrical removed"
