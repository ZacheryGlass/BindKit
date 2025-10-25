# BindKit

A modular PyQt6 desktop application that runs as a system tray utility, managing and executing desktop scripts with global hotkey support and flexible execution strategies.

## Features

### Core Functionality
- **System Tray Interface**: Primary interface via system tray icon with dynamic context menus
- **Auto-Script Discovery**: Automatically detects and loads scripts from the `scripts` directory
- **Dual Script Support**: Both legacy UtilityScript classes and modern standalone Python scripts
- **Real-time Status**: Live status updates for scripts in tray menus
- **Error Isolation**: Individual script failures don't crash the application

### Global Hotkey System
- **Windows API Integration**: Native global hotkey support using Windows RegisterHotKey API
- **Flexible Key Combinations**: Support for Ctrl, Alt, Shift, Win modifiers with any key
- **Conflict Detection**: Automatic detection of reserved system hotkeys and conflicts
- **Persistent Storage**: Hotkey mappings saved in Windows Registry
- **Real-time Configuration**: Hotkey recording interface with instant validation

### Script Execution
- **Multiple Strategies**: Subprocess, function call, and module execution based on script structure
- **AST Analysis**: Automatic script analysis to determine optimal execution strategy
- **Command Line Support**: Standalone scripts fully compatible with direct command line execution
- **Argument Detection**: Automatic detection of argparse arguments and function parameters
- **JSON Communication**: Structured result communication between scripts and GUI

### Scheduled Execution
- **Interval-based Scheduling**: Execute scripts at fixed intervals from 10 seconds to ~24.8 days
- **Overlap Prevention**: Reliably prevents simultaneous executions of the same script
- **Auto-start**: Enabled schedules automatically launch on application startup
- **Per-script Configuration**: Set schedules individually in Settings dialog Schedule tab

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Application

```bash
# Standard startup (shows in system tray)
python main.py

# Start minimized to tray with notification
python main.py --minimized

# From virtual environment
venv\Scripts\activate
python main.py
```

### Using Scripts

1. **System Tray Menu**: Right-click the tray icon to access all scripts
2. **Global Hotkeys**: Configure hotkeys in Settings → Hotkeys tab
3. **Command Line**: Execute standalone scripts directly (see examples below)

### Configuring Hotkeys

1. Right-click the system tray icon
2. Select "Settings..."
3. Go to the "Hotkeys" tab
4. Click on a script's hotkey cell and press your desired key combination
5. Click "OK" to save

Example hotkey combinations:
- `Ctrl+Alt+V` - Volume control
- `Win+Shift+D` - Display toggle
- `Ctrl+Alt+F1` - Custom script

### Configuring Schedules

1. Right-click the system tray icon
2. Select "Settings..."
3. Go to the "Schedule" tab
4. Select a script from the list
5. Check "Enable Schedule" to activate scheduling
6. Set the execution interval:
   - Choose a time value (1-999999)
   - Select unit: seconds, minutes, hours, or days
   - Minimum interval: 10 seconds (prevents excessive load)
   - Maximum interval: ~24.8 days
7. View execution times:
   - **Last run**: Shows when the script last executed (or "Never" if not yet run)
   - **Next run**: Shows the time of the next scheduled execution
8. Click "Run Now" to manually trigger the script for testing
9. Click "OK" to save schedule settings

Schedules persist across application restarts and will automatically resume when BindKit starts.

## Creating Custom Scripts

The application supports two types of scripts:

### Legacy UtilityScript (Class-based)

Create a Python file in the `scripts` directory:

```python
from core.base_script import UtilityScript
from core.button_types import ButtonType

class MyScript(UtilityScript):
    def get_metadata(self):
        return {
            'name': 'My Script',
            'description': 'Description here',
            'button_type': ButtonType.RUN
        }
    
    def get_status(self):
        return "Ready"
    
    def execute(self, *args, **kwargs):
        # Your script logic here
        return {'success': True, 'message': 'Done!'}
    
    def validate(self):
        return True  # Check if script can run on this system
```

### Standalone Scripts (Modern Approach)

Create a regular Python script with command-line support:

```python
#!/usr/bin/env python3
"""Standalone script example"""
import argparse
import json
import sys

def main():
    parser = argparse.ArgumentParser(description='My utility script')
    parser.add_argument('--action', choices=['start', 'stop'], 
                       default='start', help='Action to perform')
    
    args = parser.parse_args()
    
    # Your script logic here
    if args.action == 'start':
        result = {'success': True, 'message': 'Service started'}
    else:
        result = {'success': True, 'message': 'Service stopped'}
    
    # Output JSON for the GUI
    print(json.dumps(result))
    return 0 if result['success'] else 1

if __name__ == '__main__':
    sys.exit(main())
```

**Advantages of each approach:**

| Feature | Legacy UtilityScript | Standalone Scripts |
|---------|--------------------|--------------------|
| **Complexity** | Higher setup | Simple functions |
| **UI Integration** | Full button types | Basic execution |
| **Command Line** | Via wrapper | Native support |
| **Hotkey Support** | ✅ | ✅ |
| **Real-time Status** | ✅ | Static name only |

## Included Scripts

The application comes with several example scripts:

- **Audio Toggle**: Mute/unmute system audio
- **Bluetooth Reset**: Reset Bluetooth adapter
- **Clipboard Executor**: Execute commands from clipboard
- **Display Toggle**: Switch between Duplicate and Extend display modes
- **Hotkey Test Popup**: Test global hotkey functionality
- **Power Plan**: Cycle through Windows power plans
- **Test Hotkey**: Verify hotkey registration (creates desktop file when triggered)
- **Test Scheduled Execution**: Verify scheduled execution by logging timestamps to a file

## Architecture

```
├── core/                     # Core infrastructure
│   ├── hotkey_manager.py     # Windows API hotkey integration
│   ├── hotkey_registry.py    # Persistent hotkey storage
│   ├── script_analyzer.py    # AST-based script analysis
│   ├── script_executor.py    # Multi-strategy script execution
│   ├── script_loader.py      # Dynamic script discovery
│   ├── schedule_runtime.py   # Scheduled execution engine
│   └── settings.py           # Application settings
├── gui/                      # PyQt6 GUI components
│   ├── tray_manager.py       # System tray interface (primary UI)
│   ├── settings_dialog.py    # Settings and configuration
│   ├── hotkey_configurator.py # Hotkey recording widgets
│   └── main_window.py        # Hidden parent window
├── views/                    # UI views and panels
│   └── schedule_view.py      # Schedule configuration interface
├── scripts/                  # Auto-discovered utility scripts
└── docs/                     # Detailed documentation
    ├── ARCHITECTURE.md       # Technical architecture details
    ├── API_REFERENCE.md      # Complete API documentation
    ├── SCRIPT_TUTORIAL.md    # Script development guide
    └── SCHEDULER_GUIDE.md    # Scheduler user and developer guide
```

**Key Components:**
- **System Tray**: Primary user interface
- **Global Hotkeys**: Windows API integration for system-wide shortcuts
- **Script Analysis**: AST parsing for intelligent script execution
- **Dual Script Support**: Both legacy classes and modern standalone scripts
- **Scheduler**: QTimer-based interval scheduling with overlap prevention

## Troubleshooting

### "Failed to load Python DLL" Error on Windows

If you encounter a "Failed to load Python DLL" error when running the BindKit executable, this is typically caused by conflicts between the bundled Python interpreter and other Python versions installed on your system.

#### Solution

1. **Check for Multiple Python Installations**: Ensure you don't have conflicting Python versions installed system-wide. BindKit includes its own Python interpreter and does not require a separate Python installation.

2. **Clear Python DLL Cache**: If the error persists after ensuring no conflicts, try clearing your system's Python cache:
   - Delete the folder: `C:\Users\<YourUsername>\AppData\Local\pyinstaller`
   - Delete temporary files: Clear your Windows temp folder (`%temp%`)

3. **Antivirus/Security Software**: Some antivirus software can interfere with DLL loading. Try adding the following to your antivirus exclusions:
   - The BindKit installation directory
   - `C:\Users\<YourUsername>\AppData\Local\Temp`

4. **Run as Administrator**: Try running BindKit as Administrator:
   - Right-click `BindKit.exe`
   - Select "Run as administrator"

5. **Clean Reinstall**: If none of the above works:
   - Uninstall BindKit completely
   - Restart your computer
   - Reinstall BindKit fresh

#### If Issues Persist

If you still encounter the error after trying these steps, please report the issue at: https://github.com/your-repo/BindKit/issues

Include the following information:
- Your Windows version (Windows 10, 11, etc.)
- Any Python installations you have on your system
- The complete error message from the popup
- Any antivirus/security software you're running
