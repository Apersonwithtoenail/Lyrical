#!/usr/bin/env bash
# install.sh — install Lyrical and its desktop integration
set -e

APP_NAME="Lyrical"
APP_ID="lyrical"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BIN_DIR="$HOME/.local/bin"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
DESKTOP_DIR="$HOME/.local/share/applications"

mkdir -p "$BIN_DIR" "$ICON_DIR" "$DESKTOP_DIR"

# 1. symlink the launcher
ln -sf "$SCRIPT_DIR/lyrical.py" "$BIN_DIR/lyrical"
chmod +x "$SCRIPT_DIR/lyrical.py"

# 2. icon
cp "$SCRIPT_DIR/assets/icon.svg" "$ICON_DIR/$APP_ID.svg"

# 3. .desktop
cat > "$DESKTOP_DIR/$APP_ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=$APP_NAME
GenericName=Live Lyrics
Comment=Terminal live lyrics for any MPRIS player
Exec=python3 $HOME/.local/bin/lyrical
Icon=$APP_ID
Terminal=true
Categories=AudioVideo;Audio;Utility;
Keywords=lyrics;music;mpris;spotify;
DESKTOP

# 4. refresh caches
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
xfce4-panel -r 2>/dev/null || true

echo "✅ $APP_NAME installed"
echo "   Run: lyrical"
echo "   Or search '$APP_NAME' in your app menu."
echo "   Uninstall with: ./uninstall.sh"
