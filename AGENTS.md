# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Conventional Commits

We use Conventional Commits for all commit messages to keep history clear and tooling-friendly.

- Format: `<type>(<scope>): <short summary>`
- Common types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `perf`, `build`.
- Optional scope: narrow area like `settings`, `executor`, `ui`.
- Body: explain the what/why; wrap at ~72 chars.
- Breaking changes: add a footer `BREAKING CHANGE: <description>`.

Examples:
- `feat(settings): hard-code status refresh interval and remove UI control`
- `fix(executor): show actual timeout value in timeout error`
- `docs(agents): note we use Conventional Commits`

When a change removes or renames a user-facing option or API, include a `BREAKING CHANGE` footer describing the migration path.

## Project Overview

BindKit is a PyQt6-based Windows system tray application that manages and executes utility scripts with global hotkey support. The application runs primarily from the system tray and provides a modular architecture for script execution.

## Development Commands

### Running the Application
```bash
# Run from project root
python main.py

# Run minimized to tray
python main.py --minimized

# With virtual environment
venv\Scripts\activate
python main.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
```

Required packages:
- PyQt6>=6.4.0 (GUI framework)
- pywin32>=305 (Windows API integration for hotkeys)
- easyocr>=1.6.0 (OCR functionality)
- Pillow>=9.0.0 (Image processing)
- pyautogui>=0.9.50 (Screen automation)

## Architecture

### Core Components

1. **System Tray Interface** (`gui/tray_manager.py`): Primary UI, all user interaction happens through the tray icon menu
2. **Hotkey System** (`core/hotkey_manager.py`): Uses Windows RegisterHotKey API for global hotkeys, stores mappings in Windows Registry
3. **Script Loader** (`core/script_loader.py`): Auto-discovers scripts from `scripts/` directory at runtime
4. **Script Analyzer** (`core/script_analyzer.py`): Uses AST parsing to determine execution strategy (subprocess, function call, or module exec)
5. **Script Executor** (`core/script_executor.py`): Executes scripts based on analyzer's strategy
6. **Settings Manager** (`core/settings.py`): Manages application settings and script configurations

### Script Architecture

The application supports two script types:

1. **Legacy UtilityScript**: Class-based scripts inheriting from a base class
2. **Standalone Scripts**: Regular Python scripts with argparse support (preferred)

Scripts communicate results via JSON output:
```python
{"success": true, "message": "Operation completed"}
```

### Execution Strategies

Based on AST analysis, scripts are executed using:
- **SUBPROCESS**: For scripts with `if __name__ == '__main__'` blocks
- **FUNCTION_CALL**: For scripts with main() functions
- **MODULE_EXEC**: For simple scripts without main blocks

## Key Development Guidelines

### Adding New Scripts

1. Place Python scripts in the `scripts/` directory
2. Use argparse for command-line arguments
3. Return JSON results for GUI integration
4. Scripts are auto-discovered on application start

### Modifying Core Components

- **Hotkey Changes**: Update both `hotkey_manager.py` (runtime) and `hotkey_registry.py` (persistence)
- **Script Discovery**: Modify `script_loader.py` for loading logic changes
- **UI Updates**: Primary interface is in `tray_manager.py`, settings dialog in `settings_dialog.py`

### Windows-Specific Considerations

- Application uses Windows Registry for hotkey persistence
- Requires Windows API calls via pywin32
- System tray integration is Windows-specific
- Global hotkeys use RegisterHotKey/UnregisterHotKey Windows APIs

## Common Tasks

### Debug Script Loading Issues
Check `script_loader.py` logs - it shows which scripts are discovered and any loading errors.

### Test Hotkey Registration
Use the included `scripts/power_plan.py` or create a simple test script that outputs to a file when triggered.

### Modify Tray Menu Structure
Edit `tray_manager.py` - the `update_tray_menu()` method builds the context menu dynamically.

## Important Files

- `main.py`: Entry point, handles single instance check
- `gui/tray_manager.py`: System tray UI and menu generation
- `core/script_loader.py`: Script discovery and loading
- `core/hotkey_manager.py`: Global hotkey registration and handling
- `core/settings.py`: Application and script settings management
- `scripts/`: Directory for all utility scripts (auto-discovered)
