#!/usr/bin/env bash

# ==============================================================================
# Maple Saturation Control - Installer & Launcher
# Automatically resolves dependencies and runs the Wayland Plasma application.
# ==============================================================================

APP_SCRIPT="./maple_saturation_control.py"
DEPS_PACMAN=("python-pyqt6" "argyllcms" "colord")
DEPS_AUR=("iccxml")

echo "=== Maple Saturation Control ==="
echo "Verifying environment dependencies..."

# Install missing repository packages
install_pacman_deps() {
    for pkg in "${DEPS_PACMAN[@]}"; do
        if ! pacman -Qi "$pkg" &> /dev/null; then
            echo "Installing missing system dependency: $pkg"
            sudo pacman -S --noconfirm "$pkg"
        else
            echo "  [OK] $pkg"
        fi
    done
}

# Install missing AUR packages
install_aur_deps() {
    for pkg in "${DEPS_AUR[@]}"; do
        if ! pacman -Qi "$pkg" &> /dev/null; then
            echo "Installing missing AUR dependency: $pkg"
            if command -v yay &> /dev/null; then
                yay -S --noconfirm "$pkg"
            elif command -v paru &> /dev/null; then
                paru -S --noconfirm "$pkg"
            else
                echo "Error: Neither 'yay' nor 'paru' was found. Please install $pkg manually."
            fi
        else
            echo "  [OK] $pkg"
        fi
    done
}

# Execute dependency resolution
install_pacman_deps
install_aur_deps

# Launch the primary python application
echo "Dependencies checked successfully. Launching application..."
if [ -f "$APP_SCRIPT" ]; then
    chmod +x "$APP_SCRIPT"
    python3 "$APP_SCRIPT"
else
    echo "Error: Primary script $APP_SCRIPT not found!"
    exit 1
fi
