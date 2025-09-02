Releasing BindKit
=============================

This guide explains how to build and publish Windows releases (portable EXE and installer) using a one‑click GitHub Actions workflow.

Overview
--------
- Source of truth: `VERSION` at repo root (semantic: `X.Y.Z`).
- The Release workflow bumps `VERSION`, creates a `vX.Y.Z` tag, builds the app with PyInstaller (using `bindkit.spec`), generates a Windows installer with Inno Setup, and attaches both artifacts to a GitHub Release.
- The installer can optionally add a Startup shortcut so the app runs at login (launches with `--minimized`).

One‑Click Release (GitHub)
-------------------------
1. Push your changes to `main`.
2. In GitHub, open the `Actions` tab → select `Release` workflow.
3. Click “Run workflow” and choose the bump type: `patch`, `minor`, or `major`.
4. The workflow will:
   - Bump `VERSION`, commit `chore(release): vX.Y.Z`, and tag `vX.Y.Z`.
   - Generate `version_info.py` so the EXE embeds proper Windows version resources.
  - Build the app via PyInstaller using `bindkit.spec` (includes `scripts/` and `style.qss`).
  - Build the Windows installer via Inno Setup.
  - Create a GitHub Release and upload both the installer and the portable EXE.

Artifacts & Locations
---------------------
- Portable EXE: `dist/BindKit/BindKit.exe`
- Installer: `installer/output/BindKit-X.Y.Z-Setup.exe`

What’s Packaged
---------------
- Spec file includes:
  - Resources: `style.qss`, `scripts/`
  - Hidden imports for PyQt6, pywin32 APIs, easyocr and common dependencies
  - Optional icon: `assets/icon.ico` (if present)
- Windows version metadata embedded from `version_info.py` (auto‑generated in CI).

Local Build (optional)
----------------------
You can build locally on Windows for testing:

1. Create the executable
   - `pip install -r requirements.txt`
   - `pip install pyinstaller`
   - `pyinstaller --noconfirm --clean bindkit.spec`

2. Create the installer
   - Install Inno Setup (https://jrsoftware.org/isinfo.php)
   - Build: `ISCC installer\bindkit.iss /DMyAppVersion=0.0.0`
   - Result: `installer/output/BindKit-<version>-Setup.exe`

Versioning
----------
- `VERSION` is the only version source; CI writes Windows version resources from it.
- We follow Conventional Commits. The bump type is manual to keep things simple. You can later switch to automated changelog/bumping with `release-please` or `python-semantic-release`.

Startup Behavior
----------------
- The installer adds a per‑user Startup shortcut (checked by default). Uncheck to opt out.
- Uninstall removes the Startup entry.

Troubleshooting
---------------
- Build time: OCR dependencies (e.g., EasyOCR/Torch) are large and increase build time.
- Missing files at runtime: Ensure data files are listed in `bindkit.spec` under `datas`.
- Packaging failures: If PyInstaller can’t find a module, add it to `hiddenimports` in the spec.
