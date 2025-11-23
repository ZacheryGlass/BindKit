# API Reference

## Schedule System

### ScheduleRuntime

Manages scheduled script execution with QTimer-based intervals.

```python
from core.schedule_runtime import ScheduleRuntime, ScheduleHandle, ScheduleState
```

#### Signals
- `schedule_started(str)`: Emitted when schedule begins (script_name)
- `schedule_stopped(str)`: Emitted when schedule ends (script_name)
- `schedule_executed(str)`: Emitted on successful execution (script_name)
- `schedule_error(str, str)`: Emitted on error (script_name, error_message)
- `schedule_execution_blocked(str)`: Emitted when overlapping execution prevented (script_name)

#### Methods

##### `start_schedule(script_name: str, script_path: Path, interval_seconds: int, execution_callback: Callable, settings_manager=None) -> ScheduleHandle`
Start a scheduled execution for a script.

**Parameters:**
- `script_name`: Name of the script (for tracking and identification)
- `script_path`: Path to the script file (for reference)
- `interval_seconds`: Interval between executions in seconds (10 to ~2.4M seconds)
- `execution_callback`: Callable invoked when schedule fires
- `settings_manager`: Optional SettingsManager for timestamp persistence

**Returns:**
- `ScheduleHandle` object for the scheduled script

**Raises:**
- `ValueError`: If interval outside valid range (10s to ~24.8 days)
- `RuntimeError`: If schedule already exists for this script

**Example:**
```python
from core.schedule_runtime import ScheduleRuntime
from pathlib import Path

schedule_runtime = ScheduleRuntime()

def on_schedule_execute(script_name: str):
    print(f"Executing {script_name}")

handle = schedule_runtime.start_schedule(
    script_name="my_script",
    script_path=Path("scripts/my_script.py"),
    interval_seconds=3600,  # 1 hour
    execution_callback=on_schedule_execute
)
```

##### `stop_schedule(script_name: str) -> bool`
Stop a scheduled execution.

**Parameters:**
- `script_name`: Name of the script to stop

**Returns:**
- `True` if schedule was stopped, `False` if not found

##### `is_scheduled(script_name: str) -> bool`
Check if a script has an active schedule.

**Parameters:**
- `script_name`: Name of the script

**Returns:**
- `True` if schedule is active, `False` otherwise

##### `get_schedule_handle(script_name: str) -> Optional[ScheduleHandle]`
Get the schedule handle for a script.

**Parameters:**
- `script_name`: Name of the script

**Returns:**
- `ScheduleHandle` if found, `None` otherwise

##### `get_all_schedules() -> Dict[str, ScheduleHandle]`
Get all active schedules.

**Returns:**
- Dictionary mapping script names to ScheduleHandle objects

##### `update_interval(script_name: str, new_interval_seconds: int) -> bool`
Update the interval for a scheduled script.

**Parameters:**
- `script_name`: Name of the script
- `new_interval_seconds`: New interval in seconds

**Returns:**
- `True` if successful, `False` if schedule not found

**Raises:**
- `ValueError`: If interval outside valid range

##### `stop_all_schedules() -> int`
Stop all active schedules (typically called on application shutdown).

**Returns:**
- Number of schedules stopped

##### `get_schedule_status(script_name: str) -> str`
Get human-readable status of a schedule.

**Parameters:**
- `script_name`: Name of the script

**Returns:**
- Status string: "Not scheduled", "Scheduled", "Running", "Stopped", or "Error"

##### `get_schedule_info(script_name: str) -> Optional[Dict[str, Any]]`
Get detailed information about a schedule.

**Parameters:**
- `script_name`: Name of the script

**Returns:**
- Dictionary with schedule info (script_name, interval_seconds, last_run, next_run, is_executing, state) or None

### Data Classes

#### ScheduleState
Enumeration of schedule states.

```python
class ScheduleState(Enum):
    STOPPED = "stopped"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    ERROR = "error"
```

#### ScheduleHandle
Tracks a scheduled script execution.

```python
@dataclass
class ScheduleHandle:
    script_name: str              # Name of the script
    script_path: Path             # Path to script file
    interval_seconds: int         # Interval between executions
    timer: QTimer                 # Qt timer object
    last_run: Optional[float]     # Timestamp of last execution
    next_run: Optional[float]     # Timestamp of next execution
    is_executing: bool            # Currently executing flag
    is_stopping: bool             # Stopping flag (prevents race conditions)
    state: ScheduleState          # Current schedule state
    execution_callback: Optional[Callable]  # Callback when scheduled
```

### ScheduleView

UI component for configuring scheduled script execution.

```python
from views.schedule_view import ScheduleView
```

#### Signals
- `schedule_enabled_changed(str, bool)`: Emitted when enabling/disabling (script_name, enabled)
- `schedule_interval_changed(str, int)`: Emitted when interval changes (script_name, interval_seconds)

#### Methods

##### `set_available_scripts(scripts: List[dict])`
Set the list of available scripts for scheduling.

**Parameters:**
- `scripts`: List of script info dicts with keys: name, display_name

##### `set_schedule_enabled(enabled: bool)`
Set the schedule enabled checkbox state.

##### `set_interval(interval_seconds: int)`
Set the interval display (converts to appropriate unit).

##### `set_last_run(timestamp: Optional[float])`
Set the last run time display.

##### `set_next_run(timestamp: Optional[float])`
Set the next run time display.

##### `set_status(status: str)`
Set the status display.

##### `update_schedule_info(script_name: str, schedule_info: dict)`
Update schedule information for display.

**Parameters:**
- `script_name`: Name of the script
- `schedule_info`: Dictionary with schedule information

## Global Hotkey System

### HotkeyManager

Manages Windows API integration for global hotkey registration.

```python
from core.hotkey_manager import HotkeyManager
```

#### Signals
- `hotkey_triggered(str, str)`: Emitted when hotkey is pressed (script_name, hotkey_string)
- `registration_failed(str, str)`: Emitted when registration fails (hotkey_string, error_message)

#### Methods

##### `register_hotkey(script_name: str, hotkey_string: str) -> bool`
Register a global hotkey for a script.

**Parameters:**
- `script_name`: Name of the script to associate with hotkey
- `hotkey_string`: Hotkey combination (e.g., "Ctrl+Alt+X")

**Returns:**
- `True` if registration succeeded, `False` otherwise

**Example:**
```python
hotkey_manager = HotkeyManager()
hotkey_manager.start()
success = hotkey_manager.register_hotkey("My Script", "Ctrl+Alt+X")
```

##### `unregister_hotkey(script_name: str) -> bool`
Unregister a hotkey for a script.

##### `validate_hotkey_string(hotkey_string: str) -> Tuple[bool, str]`
Validate a hotkey string for format and conflicts.

**Returns:**
- Tuple of (is_valid, error_message)

### HotkeyRegistry

Manages persistent storage of hotkey mappings.

```python
from core.hotkey_registry import HotkeyRegistry
```

#### Signals
- `hotkey_added(str, str)`: Emitted when hotkey is added (script_name, hotkey_string)
- `hotkey_removed(str)`: Emitted when hotkey is removed (script_name)
- `hotkey_updated(str, str, str)`: Emitted when hotkey changes (script_name, old_hotkey, new_hotkey)

#### Methods

##### `add_hotkey(script_name: str, hotkey_string: str) -> Tuple[bool, str]`
Add or update a hotkey mapping.

**Returns:**
- Tuple of (success, error_message)

##### `remove_hotkey(script_name: str) -> bool`
Remove a hotkey mapping for a script.

##### `get_all_mappings() -> Dict[str, str]`
Get all hotkey mappings as script_name -> hotkey_string dictionary.

## Script Analysis & Execution System

### ScriptAnalyzer

Analyzes Python scripts to determine execution strategies.

```python
from core.script_analyzer import ScriptAnalyzer, ScriptInfo
```

#### Methods

##### `analyze_script(script_path: Path) -> ScriptInfo`
Analyze a Python script and return execution information.

**Returns:**
- `ScriptInfo` object containing analysis results

**Example:**
```python
analyzer = ScriptAnalyzer()
script_info = analyzer.analyze_script(Path("my_script.py"))
print(f"Execution strategy: {script_info.execution_strategy}")
print(f"Arguments: {[arg.name for arg in script_info.arguments]}")
```

### ScriptExecutor

Executes scripts using multiple strategies.

```python
from core.script_executor import ScriptExecutor, ExecutionResult
```

#### Methods

##### `execute_script(script_info: ScriptInfo, arguments: Optional[Dict[str, Any]] = None) -> ExecutionResult`
Execute a script using the appropriate strategy.

**Parameters:**
- `script_info`: ScriptInfo object from ScriptAnalyzer
- `arguments`: Dictionary of arguments to pass to script

**Returns:**
- `ExecutionResult` with success, message, output, error, and data

**Example:**
```python
executor = ScriptExecutor()
result = executor.execute_script(script_info, {"arg1": "value1"})
if result.success:
    print(f"Success: {result.message}")
else:
    print(f"Error: {result.error}")
```

##### `validate_arguments(script_info: ScriptInfo, arguments: Dict[str, Any]) -> List[str]`
Validate arguments against script requirements.

**Returns:**
- List of validation error messages (empty if valid)

### Data Classes

#### ScriptInfo
Information about an analyzed script.

```python
@dataclass
class ScriptInfo:
    file_path: Path
    display_name: str
    execution_strategy: ExecutionStrategy
    main_function: Optional[str] = None
    arguments: List[ArgumentInfo] = None
    has_main_block: bool = False
    is_executable: bool = False
    error: Optional[str] = None
```

#### ExecutionResult
Result of script execution.

```python
@dataclass
class ExecutionResult:
    success: bool
    message: str = ""
    output: str = ""
    error: str = ""
    return_code: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
```

#### ArgumentInfo
Information about a script argument.

```python
@dataclass
class ArgumentInfo:
    name: str
    required: bool = False
    default: Any = None
    help: str = ""
    type: str = "str"
    choices: Optional[List[str]] = None
```

## Core Module

### UtilityScript

Base class for all utility scripts.

```python
from core.base_script import UtilityScript
```

#### Methods

##### `get_metadata() -> Dict[str, Any]`
Returns script metadata for UI generation.

**Returns:**
- `name` (str): Display name of the script
- `description` (str): Brief description
- `button_type` (ButtonType): Type of UI control
- `button_options` (ButtonOptions, optional): Configuration for the button

**Example:**
```python
def get_metadata(self):
    return {
        'name': 'Network Toggle',
        'description': 'Enable/disable network adapter',
        'button_type': ButtonType.TOGGLE,
        'button_options': ToggleOptions(
            on_label="Connected",
            off_label="Disconnected"
        )
    }
```

##### `get_status() -> Any`
Returns current status without side effects.

**Returns:**
- Status value appropriate for the button type
  - Toggle: `bool`
  - Cycle: `str` (current option)
  - Slider: `float/int`
  - Select: `str` (selected option)

**Example:**
```python
def get_status(self):
    return self.is_network_enabled()
```

##### `execute(*args, **kwargs) -> Dict[str, Any]`
Executes the script action.

**Parameters:**
- `*args`: Positional arguments from UI control
- `**kwargs`: Keyword arguments from UI control

**Returns:**
- `success` (bool): Whether execution succeeded
- `message` (str, optional): User-friendly message
- `new_status` (Any, optional): Updated status value

**Example:**
```python
def execute(self, enabled):
    if self.set_network_state(enabled):
        return {
            'success': True,
            'message': f'Network {"enabled" if enabled else "disabled"}'
        }
    return {'success': False, 'message': 'Failed to change network state'}
```

##### `validate() -> bool`
Checks if script can run on current system.

**Returns:**
- `True` if script is compatible with system
- `False` otherwise

**Example:**
```python
def validate(self):
    return sys.platform == 'win32' and self.has_admin_rights()
```

### ButtonType

Enumeration of available button types.

```python
from core.button_types import ButtonType
```

| Value | Description |
|-------|-------------|
| `ButtonType.RUN` | Simple execution button |
| `ButtonType.TOGGLE` | Two-state toggle |
| `ButtonType.CYCLE` | Cycle through multiple options |
| `ButtonType.SELECT` | Dropdown selection |
| `ButtonType.NUMBER` | Numeric input |
| `ButtonType.SLIDER` | Range slider |
| `ButtonType.TEXT_INPUT` | Text input field |
| `ButtonType.CONFIRM` | Confirmation button |

### Button Options

Configuration classes for each button type.

#### ToggleOptions
```python
from core.button_types import ToggleOptions

options = ToggleOptions(
    on_label="On",        # Label when toggled on
    off_label="Off",      # Label when toggled off
    show_status=True      # Show status in button
)
```

#### CycleOptions
```python
from core.button_types import CycleOptions

options = CycleOptions(
    options=["Low", "Medium", "High"],  # List of options to cycle
    show_current=True                   # Show current option
)
```

#### SelectOptions
```python
from core.button_types import SelectOptions

options = SelectOptions(
    options=["Option1", "Option2"],  # Dropdown options
    placeholder="Select..."          # Placeholder text
)
```

#### NumberOptions
```python
from core.button_types import NumberOptions

options = NumberOptions(
    min_value=0,      # Minimum value (optional)
    max_value=100,    # Maximum value (optional)
    step=1.0,         # Step increment
    decimals=0,       # Decimal places
    suffix="%"        # Display suffix
)
```

#### SliderOptions
```python
from core.button_types import SliderOptions

options = SliderOptions(
    min_value=0,      # Minimum value
    max_value=100,    # Maximum value
    step=1,           # Step increment
    show_value=True,  # Show current value
    suffix="%"        # Display suffix
)
```

#### TextInputOptions
```python
from core.button_types import TextInputOptions

options = TextInputOptions(
    placeholder="Enter text...",  # Placeholder text
    max_length=100,               # Maximum length (optional)
    multiline=False               # Enable multiline
)
```

#### RunOptions
```python
from core.button_types import RunOptions

options = RunOptions(
    button_text="Execute",           # Button label
    confirm_before_run=False,        # Require confirmation
    confirm_message="Are you sure?"  # Confirmation message
)
```

### ScriptLoader

Handles dynamic script discovery and loading.

```python
from core.script_loader import ScriptLoader

loader = ScriptLoader(scripts_directory="scripts")
```

#### Methods

##### `discover_scripts() -> List[UtilityScript]`
Discovers and loads all valid scripts.

**Returns:**
- List of loaded UtilityScript instances

##### `reload_scripts() -> List[UtilityScript]`
Clears cache and reloads all scripts.

**Returns:**
- List of reloaded UtilityScript instances

##### `get_script(name: str) -> Optional[UtilityScript]`
Gets a loaded script by name.

**Parameters:**
- `name`: Script filename without extension

**Returns:**
- UtilityScript instance or None

##### `get_failed_scripts() -> Dict[str, str]`
Gets scripts that failed to load.

**Returns:**
- Dictionary mapping filename to error message

### Exceptions

Custom exceptions for error handling.

```python
from core.exceptions import (
    ScriptError,           # Base exception
    ScriptLoadError,       # Loading failed
    ScriptExecutionError,  # Execution failed
    ScriptValidationError, # Validation failed
    ScriptTimeoutError     # Operation timed out
)
```

## GUI Module

### TrayManager

Primary system tray interface.

```python
from gui.tray_manager import TrayManager

tray_manager = TrayManager(parent_window)
```

#### Signals
- `settings_requested`: Emitted when user requests settings
- `exit_requested`: Emitted when user requests application exit

#### Methods

##### `set_script_loader(script_loader: ScriptLoader)`
Set the script loader for dynamic script discovery.

##### `refresh_scripts()`
Update the tray menu with current scripts and their status.

##### `refresh_hotkeys()`
Update hotkey registrations based on current settings.

##### `execute_script_by_name(script_name: str)`
Execute a script by name (typically called from hotkey).

##### `show_notification(title: str, message: str)`
Display a system tray notification.

**Example:**
```python
tray_manager = TrayManager(main_window)
tray_manager.set_script_loader(script_loader)
tray_manager.show_notification("Success", "Script executed successfully")
```

### MainWindow

Minimal main window for settings and dialogs.

```python
from gui.main_window import MainWindow

window = MainWindow()
```

#### Signals
- `scripts_reloaded`: Emitted when scripts are reloaded
- `settings_changed`: Emitted when application settings change
- `hotkeys_changed`: Emitted when hotkey mappings change

#### Methods

##### `open_settings()`
Open the settings dialog.

##### `load_scripts()`
Load all scripts from the scripts directory.

### HotkeyConfigurator

GUI components for hotkey configuration.

```python
from gui.hotkey_configurator import HotkeyRecorder, HotkeyConfigDialog
```

#### HotkeyRecorder

Custom QLineEdit for recording key combinations.

**Signals:**
- `hotkey_changed(str)`: Emitted when hotkey combination changes

**Methods:**
- `start_recording()`: Begin capturing key combinations
- `stop_recording()`: End key combination capture
- `get_hotkey() -> str`: Get current hotkey string
- `set_hotkey(hotkey_string: str)`: Set displayed hotkey

#### HotkeyConfigDialog

Dialog for configuring hotkeys for scripts.

```python
dialog = HotkeyConfigDialog("Script Name", current_hotkey="Ctrl+Alt+X")
if dialog.exec() == QDialog.DialogCode.Accepted:
    new_hotkey = dialog.get_hotkey()
```

### SettingsDialog

Enhanced settings dialog with hotkey support.

```python
from gui.settings_dialog import SettingsDialog

dialog = SettingsDialog(parent)
```

The settings dialog includes tabbed interface for:
- General application settings
- Script configuration 
- Hotkey management with real-time validation
- Font and appearance settings

## Complete Script Examples

### Legacy UtilityScript Example

```python
import sys
import subprocess
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.append('..')

from core.base_script import UtilityScript
from core.button_types import ButtonType, SliderOptions

class BrightnessControl(UtilityScript):
    """Adjust screen brightness on Windows."""
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            'name': 'Screen Brightness',
            'description': 'Adjust display brightness',
            'button_type': ButtonType.SLIDER,
            'button_options': SliderOptions(
                min_value=20,
                max_value=100,
                step=5,
                show_value=True,
                suffix="%"
            )
        }
    
    def get_status(self) -> int:
        """Get current brightness level."""
        try:
            # PowerShell command to get brightness
            cmd = '(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness'
            result = subprocess.run(
                ['powershell', '-Command', cmd],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
        except Exception:
            pass
        return 50  # Default
    
    def execute(self, brightness: float) -> Dict[str, Any]:
        """Set brightness level."""
        try:
            brightness = int(brightness)
            
            # PowerShell command to set brightness
            cmd = f'(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{brightness})'
            result = subprocess.run(
                ['powershell', '-Command', cmd],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': f'Brightness set to {brightness}%'
                }
        except Exception as e:
            return {
                'success': False,
                'message': f'Failed to set brightness: {str(e)}'
            }
    
    def validate(self) -> bool:
        """Check if brightness control is available."""
        if sys.platform != 'win32':
            return False
        
        try:
            # Check if WMI brightness control is available
            cmd = 'Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness'
            result = subprocess.run(
                ['powershell', '-Command', cmd],
                capture_output=True,
                timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except Exception:
            return False
```

### Standalone Script Example

```python
#!/usr/bin/env python3
"""
Standalone script for network interface control.
Can be executed via tray menu, hotkeys, or command line.
"""
import argparse
import subprocess
import sys
import json

def get_network_status():
    """Get current network interface status"""
    try:
        result = subprocess.run(
            ['netsh', 'interface', 'show', 'interface'],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        return 'connected' in result.stdout.lower()
    except Exception:
        return False

def toggle_network(enable: bool):
    """Enable or disable network interface"""
    try:
        action = 'enable' if enable else 'disable'
        result = subprocess.run(
            ['netsh', 'interface', 'set', 'interface', 'Ethernet', action],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        if result.returncode == 0:
            return {
                'success': True,
                'message': f'Network {"enabled" if enable else "disabled"}'
            }
        else:
            return {
                'success': False,
                'message': f'Failed to {action} network: {result.stderr}'
            }
    except Exception as e:
        return {
            'success': False,
            'message': f'Error: {str(e)}'
        }

def main():
    """Main function - can be called by ScriptExecutor"""
    parser = argparse.ArgumentParser(description='Control network interface')
    parser.add_argument('--enable', action='store_true', 
                       help='Enable network interface')
    parser.add_argument('--disable', action='store_true',
                       help='Disable network interface')
    parser.add_argument('--status', action='store_true',
                       help='Show current status')
    
    args = parser.parse_args()
    
    if args.status:
        status = get_network_status()
        result = {
            'success': True,
            'message': f'Network is {"connected" if status else "disconnected"}',
            'data': {'connected': status}
        }
    elif args.enable:
        result = toggle_network(True)
    elif args.disable:
        result = toggle_network(False)
    else:
        # Default action - toggle
        current_status = get_network_status()
        result = toggle_network(not current_status)
    
    # Output JSON for ScriptExecutor to parse
    print(json.dumps(result))
    return 0 if result['success'] else 1

if __name__ == '__main__':
    sys.exit(main())
```

### Using the Analysis & Execution System

```python
from pathlib import Path
from core.script_analyzer import ScriptAnalyzer
from core.script_executor import ScriptExecutor

# Analyze a standalone script
analyzer = ScriptAnalyzer()
script_info = analyzer.analyze_script(Path('network_control.py'))

print(f"Script: {script_info.display_name}")
print(f"Strategy: {script_info.execution_strategy}")
print(f"Arguments: {[arg.name for arg in script_info.arguments]}")

# Execute the script
executor = ScriptExecutor()
result = executor.execute_script(script_info, {'enable': True})

if result.success:
    print(f"Success: {result.message}")
    if result.data:
        print(f"Data: {result.data}")
else:
    print(f"Error: {result.error}")
```

## Logging

Access loggers for debugging:

```python
import logging

# Get specific logger
logger = logging.getLogger('GUI.MainWindow')
logger.info("Custom log message")

# Available loggers:
# - 'MAIN'
# - 'GUI.MainWindow'
# - 'GUI.ScriptWidget'
# - 'GUI.ButtonFactory'
# - 'Core.ScriptLoader'
```