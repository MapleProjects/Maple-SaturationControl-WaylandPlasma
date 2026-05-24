# Maple Saturation & Contrast Control for KDE Plasma (Wayland)

A modern, native display color management utility designed to adjust screen saturation (digital vibrance) and contrast gamma curves in real-time under **KDE Plasma 6 Wayland** environments.

![Design Preview](file:///home/rick/.gemini/antigravity-ide/brain/1b912710-2413-414d-a323-e0eb13c9c181/media__1779661743490.png)

## Key Features

- **Dynamic Color Saturation:** Smooth sliders and precise stepper controls to adjust display saturation (from grayscale to 400% vividness).
- **Contrast Gamma Control:** Fine-tune contrast gamma curves dynamically to enhance readability, contrast, and depth.
- **KWin Wayland Native integration:** Uses native ArgyllCMS and colord pipelines via `kscreen-doctor` to avoid lagging external overlays or heavy GPU filters.
- **Alternating Double-Profile Cache:** Dynamically cycles between two fixed active profiles (`maple_active_a.icc` and `maple_active_b.icc`) to bypass KWin color cache limitations in real-time, preventing temporary file build-up.
- **Modern Premium Design System:** Gorgeous, cohesive dark-mode user interface utilizing custom HSL palettes, smooth micro-interactions, and step adjustments.
- **Startup Restore Support:** Runs seamlessly in the background or applies saved configurations instantly at system login via the `--apply` CLI parameter.

---

## Installation & Deployment

### Dependencies

Ensure the following packages are installed on your Arch Linux system:
- `python` & `python-pyqt6` (App environment and GUI layer)
- `argyllcms` & `colord` (Color management framework engines)
- `iccxml` (ICC profile compiler toolset)

### Method 1: Using the Desktop Launcher (Local)
Run the `start_app.sh` script to automatically check/install dependencies via Pacman or your AUR helper (`yay`/`paru`) and launch the application:
```bash
chmod +x start_app.sh
./start_app.sh
```

### Method 2: System-wide AUR Installation (Local Test Build)
You can compile and build the package locally using the provided standard Arch Linux `PKGBUILD` recipe:
```bash
# Clone the directory, navigate to it, and compile the package
makepkg -si
```

---

## Command Line Interface (CLI)

Maple Saturation Control comes with a silent startup command that is perfect for script execution or autostart items:

```bash
# Instantly restore and apply your saved color parameters at system login:
maple-saturation-control --apply
```

---

## AUR Publishing Guide

To publish this package onto the Arch User Repository (AUR), follow these simple steps:

1. **Host Source Code on GitHub:**
   - Create a public repository at `https://github.com/RickStylesProyects/Maple-SaturationControl-WaylandPlasma`.
   - Push your script `maple_saturation_control.py` and the `MapleSaturation.desktop` file to the main branch.

2. **Initialize Empty AUR Repo:**
   - Log into your AUR account on [aur.archlinux.org](https://aur.archlinux.org/).
   - Set up your SSH public key in your account settings.
   - Clone the package repository (it will be empty at first):
     ```bash
     git clone ssh://aur@aur.archlinux.org/maple-saturation-control-git.git
     cd maple-saturation-control-git
     ```

3. **Assemble the PKGBUILD & SRCINFO:**
   - Copy the provided `PKGBUILD` file into the cloned `maple-saturation-control-git` directory.
   - Run the command to generate the standard `.SRCINFO` metadata file:
     ```bash
     makepkg --printsrcinfo > .SRCINFO
     ```

4. **Commit & Push to AUR:**
   - Stage and commit both files:
     ```bash
     git add PKGBUILD .SRCINFO
     git commit -m "Initial release of Maple Saturation Control for Plasma Wayland"
     git push origin master
     ```

Your package will now be searchable and ready to install by anyone using a standard AUR helper:
```bash
yay -S maple-saturation-control-git
```
