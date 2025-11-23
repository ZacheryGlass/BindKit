## Conventional Commits

We use Conventional Commits for all commit messages to keep history clear and tooling-friendly.

- Format: `<type>(<scope>): <short summary>`
- Common types: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `perf`, `build`.
- Optional scope: narrow area like `settings`, `executor`, `ui`.
- Body: explain the what/why; wrap at ~72 chars.
- Breaking changes: add a footer `BREAKING CHANGE: <description>`.
- Never add Claude as the commit author. Never mention "Claude Code" in the commit message.

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
7. **Schedule Runtime** (`core/schedule_runtime.py`): QTimer-based interval scheduling engine that manages automatic periodic script execution with overlap prevention, interval bounds (10s to ~24.8 days), and graceful shutdown handling

### Script Architecture

The application supports two script types:

1. **Legacy UtilityScript**: Class-based scripts inheriting from a base class
2. **Standalone Scripts**: Regular Python scripts with argparse support (preferred)

Scripts communicate results via JSON output:
```python
{"success": true, "message": "Operation completed"}
```

### Execution Strategy

All Python scripts execute as isolated subprocesses:
- **SUBPROCESS**: All Python scripts run in separate processes for UI safety and isolation
- **SERVICE**: Long-running background scripts configured as services
- **POWERSHELL/BATCH/SHELL**: Non-Python scripts execute via their respective interpreters

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
Use one of the included scripts in `scripts/` (for example `snipping_tool.py`) or create a simple test script that outputs to a file when triggered.

### Modify Tray Menu Structure
Edit `tray_manager.py` - the `update_tray_menu()` method builds the context menu dynamically.

## Scheduled Script Execution

The scheduler enables time-based execution of scripts at regular intervals, with features for reliability and configuration:

### Configuration
- Access via Settings dialog > Schedule tab
- Enable/disable schedules on a per-script basis
- Configure intervals in seconds, minutes, hours, or days
- Minimum interval: 10 seconds; Maximum: ~24.8 days
- Settings persist across application restarts

### Key Features
- **Overlap Prevention**: Prevents simultaneous executions of the same script, ensuring reliability and resource management
- **Interval-based Scheduling**: Execute scripts at fixed time intervals without external dependencies
- **Auto-start**: Enabled schedules automatically start when the application launches
- **Timestamp Tracking**: Monitors last run and next scheduled run times
- **Signal-based Events**: Real-time notifications via schedule_started, schedule_stopped, schedule_executed, schedule_error, and schedule_execution_blocked signals
- **Thread-safe Operations**: Uses locks for race condition prevention and graceful concurrent access

### Usage
1. Right-click the system tray icon and select "Settings..."
2. Go to the "Schedule" tab
3. Select a script from the list
4. Check "Enable Schedule" to activate scheduling
5. Set the interval using the spinbox and unit dropdown
6. View "Last run" and "Next run" timestamps to monitor execution

## Important Files

- `main.py`: Entry point, handles single instance check
- `gui/tray_manager.py`: System tray UI and menu generation
- `core/script_loader.py`: Script discovery and loading
- `core/hotkey_manager.py`: Global hotkey registration and handling
- `core/settings.py`: Application and script settings management
- `core/schedule_runtime.py`: Scheduled script execution engine
- `views/schedule_view.py`: Schedule configuration UI
- `scripts/`: Directory for all utility scripts (auto-discovered)