#!/usr/bin/env bash
# install.sh — install Lyrical to ~/.local/bin + app menu
set -e

APP_NAME="Lyrical"
APP_ID="lyrical"
SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lyrical.py"

BIN="$HOME/.local/bin"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
APPS="$HOME/.local/share/applications"
mkdir -p "$BIN" "$ICONS" "$APPS"

[ -f "$SCRIPT" ] || { echo "❌ missing: $SCRIPT"; exit 1; }
chmod +x "$SCRIPT"

# 🔑 critical: remove any existing file/symlink FIRST, otherwise `cat >`
# follows a symlink and clobbers the real source file.
rm -f "$BIN/$APP_ID"

cat > "$BIN/$APP_ID" <<WRAP
#!/usr/bin/env bash
/usr/bin/python3 "$SCRIPT" "\$@"
WRAP
chmod +x "$BIN/$APP_ID"

# icon
cp "$(dirname "$SCRIPT")/assets/icon.svg" "$ICONS/$APP_ID.svg"

# .desktop
cat > "$APPS/$APP_ID.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=$APP_NAME
GenericName=Live Lyrics
Comment=Terminal live lyrics for any MPRIS player
Exec=$BIN/$APP_ID
Icon=$APP_ID
Terminal=true
Categories=AudioVideo;Audio;Utility;
Keywords=lyrics;music;mpris;spotify;
DESKTOP

update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "✅ $APP_NAME installed"
echo "   Run from terminal:  $APP_ID"
echo "   Or search the app menu."
echo "   Uninstall:          ./uninstall.sh"
