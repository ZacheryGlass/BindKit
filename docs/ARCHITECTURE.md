# BindKit - Architecture Documentation

## Table of Contents
1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
4. [Schedule Runtime System](#schedule-runtime-system)
5. [GUI Components](#gui-components)
6. [Script System](#script-system)
7. [Communication Flow](#communication-flow)
8. [Error Handling](#error-handling)
9. [Logging System](#logging-system)

## Overview

BindKit is a modular PyQt6 application that automatically discovers and manages desktop utility scripts. It provides a dynamic, extensible interface where scripts can define their own UI controls and behaviors.

### Key Design Principles
- **Modularity**: Scripts are independent modules that can be added/removed without affecting the core system
- **Dynamic Discovery**: Scripts are automatically detected and loaded from the scripts directory
- **Error Isolation**: Individual script failures don't crash the application
- **Type Safety**: Strong typing through button types and options
- **Observable State**: Real-time status updates and logging

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            Main Application                               │
│                     (main.py + SingleApplication)                        │
└────────────────┬──────────────────┬──────────────────────────────────────┘
                 │                  │
        ┌────────▼──────┐    ┌──────▼────────────────────────────────┐
        │  GUI Layer    │    │          Core Services              │
        │ (PyQt6)       │    │                                     │
        ├───────────────┤    ├─────────────────────────────────────┤
        │• TrayManager  │◄───┤• HotkeyManager (Windows API)       │
        │• MainWindow   │    │• HotkeyRegistry (Settings)          │
        │• SettingsDialog│    │• ScriptAnalyzer (AST)               │
        │• HotkeyConfig │    │• ScriptExecutor (Multi-strategy)    │
        │• ThemeManager │    │• ScriptLoader (Discovery)           │
        │• ScheduleView │    │• ScheduleRuntime (QTimer)            │
        └───────┬───────┘    │• Settings & StartupManager         │
                │            └─────┬───────────────────────────────┘
                │                  │
                └──────────────────┼─────────────────────┐
                                   │                     │
        ┌──────────────────────────▼──────────┐    ┌────▼────────────────┐
        │          Script System              │    │   Global Hotkeys   │
        │                                     │    │                    │
        ├─────────────────────────────────────┤    ├────────────────────┤
        │• Legacy UtilityScript (Inherit)     │    │• Win32 API Hook    │
        │• Standalone Scripts (AST Analysis)  │    │• Key Combinations  │
        │• Mixed Execution Strategies:        │    │• Script Triggers   │
        │  - Subprocess (argparse)            │    │• Registry Storage  │
        │  - Function Call (main function)    │    │• Conflict Detection│
        │  - Module Execution (import)        │    │• System Reserved   │
        └─────────────────────────────────────┘    └────────────────────┘
                                   │
                          ┌────────▼────────────┐
                          │  Schedule System    │
                          │                    │
                          ├────────────────────┤
                          │• QTimer-based      │
                          │• Interval Schedule │
                          │• Overlap Prevention│
                          │• Timestamp Track   │
                          └────────────────────┘
```

## Core Components

### 1. Global Hotkey System

#### HotkeyManager (`core/hotkey_manager.py`)
Manages Windows API integration for global hotkey registration.

**Key Features**:
- Windows RegisterHotKey/UnregisterHotKey API integration
- Hidden Qt widget for receiving WM_HOTKEY messages
- Support for modifier combinations (Ctrl, Alt, Shift, Win)
- Automatic conflict detection and system-reserved key blocking
- Real-time hotkey validation and normalization

```python
class HotkeyManager(QObject):
    hotkey_triggered = pyqtSignal(str, str)  # script_name, hotkey_string
    registration_failed = pyqtSignal(str, str)  # hotkey_string, error_message
    
    def register_hotkey(self, script_name: str, hotkey_string: str) -> bool
    def unregister_hotkey(self, script_name: str) -> bool
    def validate_hotkey_string(self, hotkey_string: str) -> Tuple[bool, str]
```

#### HotkeyRegistry (`core/hotkey_registry.py`)
Manages persistent storage of hotkey mappings in QSettings.

**Key Features**:
- Persistent hotkey-to-script mapping storage
- Conflict detection and validation
- Orphaned hotkey cleanup when scripts are removed
- Import/export functionality for backup and sharing

```python
class HotkeyRegistry(QObject):
    def add_hotkey(self, script_name: str, hotkey_string: str) -> Tuple[bool, str]
    def remove_hotkey(self, script_name: str) -> bool
    def validate_mappings(self, script_loader: ScriptLoader) -> List[str]
```

### 2. Script Analysis & Execution System

#### ScriptAnalyzer (`core/script_analyzer.py`)
AST-based analysis of Python scripts to determine execution strategies.

**Key Features**:
- Automatic script structure analysis using Python AST
- Argument detection from argparse or function signatures
- Execution strategy determination (subprocess, function call, module exec)
- Support for both legacy UtilityScript and standalone scripts

```python
class ScriptAnalyzer:
    def analyze_script(self, script_path: Path) -> ScriptInfo
    def _extract_argparse_arguments(self, tree: ast.AST) -> List[ArgumentInfo]
    def _determine_execution_strategy(self, has_main_function: bool, 
                                    has_main_block: bool, 
                                    arguments: List[ArgumentInfo]) -> ExecutionStrategy
```

#### ScriptExecutor (`core/script_executor.py`)
Flexible script execution engine supporting multiple strategies.

**Execution Strategies**:
- **SUBPROCESS**: Execute via subprocess with command-line arguments
- **FUNCTION_CALL**: Import and call main function directly  
- **MODULE_EXEC**: Import and execute entire module

```python
class ScriptExecutor:
    def execute_script(self, script_info: ScriptInfo, 
                      arguments: Optional[Dict[str, Any]] = None) -> ExecutionResult
    def validate_arguments(self, script_info: ScriptInfo, 
                          arguments: Dict[str, Any]) -> List[str]
```

### 3. Legacy UtilityScript Base Class (`core/base_script.py`)

Abstract base class for backward compatibility with existing scripts.

```python
class UtilityScript(ABC):
    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]
    # Returns: name, description, button_type, button_options
    
    @abstractmethod
    def get_status(self) -> Any
    # Returns current status without executing action
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Dict[str, Any]
    # Executes the script action
    # Returns: {'success': bool, 'message': str, 'new_status': Any}
    
    @abstractmethod
    def validate(self) -> bool
    # Checks if script can run on this system
```

### 2. ButtonTypes (`core/button_types.py`)

Defines all supported interaction types:

| ButtonType | Description | User Interaction |
|------------|-------------|------------------|
| `RUN` | One-time execution | Click button |
| `TOGGLE` | Boolean on/off state | Toggle between two states |
| `CYCLE` | Cycle through options | Click to advance to next option |
| `SELECT` | Dropdown selection | Choose from dropdown |
| `NUMBER` | Numeric input | Enter number in spinbox |
| `SLIDER` | Range selection | Drag slider |
| `TEXT_INPUT` | Text entry | Type text and submit |
| `CONFIRM` | Confirmation action | Click to execute with confirmation |

Each button type has corresponding options (e.g., `ToggleOptions`, `SliderOptions`) that configure its behavior.

### 3. ScriptLoader (`core/script_loader.py`)

Responsible for dynamic script discovery and management:

- **Discovery**: Scans scripts directory for Python files
- **Loading**: Imports modules and instantiates UtilityScript classes
- **Validation**: Ensures scripts pass validation before loading
- **Error Isolation**: Catches and logs individual script failures
- **Hot Reload**: Can reload scripts without restarting application

## Schedule Runtime System

### ScheduleRuntime (`core/schedule_runtime.py`)

QTimer-based scheduling engine for periodic script execution with emphasis on reliability and simplicity.

**Architecture:**
- **Timer-based Execution**: Uses Qt's QTimer for interval-based scheduling without external cron dependencies
- **Thread-safe Operations**: Uses locks (threading.Lock) to prevent race conditions during schedule operations
- **Interval Validation**: Enforces bounds (10 seconds minimum, ~24.8 days maximum) to prevent system overload
- **Overlap Prevention**: Built-in execution overlap detection prevents concurrent execution of the same script
- **Graceful Lifecycle**: Proper initialization, cleanup, and shutdown handling

**Key Features:**
- Schedule state management with ScheduleState enum (STOPPED, SCHEDULED, RUNNING, ERROR)
- ScheduleHandle dataclass for tracking individual schedules with metadata
- Signal-based event system for integration with application components
- Persistent scheduling across application restarts (via SettingsManager)

**Signals:**
- `schedule_started(str)`: Emitted when schedule begins (script_name)
- `schedule_stopped(str)`: Emitted when schedule ends (script_name)
- `schedule_executed(str)`: Emitted on successful execution (script_name)
- `schedule_error(str, str)`: Emitted on error (script_name, error_message)
- `schedule_execution_blocked(str)`: Emitted when overlapping execution prevented (script_name)

**Integration:**
- Connects with ScriptExecutor to trigger actual script execution
- Updates SettingsManager with execution timestamps for persistence
- Works with ScheduleView for UI configuration
- Managed by MainWindow for application lifecycle coordination

### ScheduleView (`views/schedule_view.py`)

UI component for configuring scheduled script execution.

**Features:**
- **Script Selection**: List of available scripts with selection state tracking
- **Enable/Disable**: Toggle scheduling per-script with immediate state updates
- **Interval Configuration**: Spinbox + unit dropdown (seconds, minutes, hours, days)
- **Status Display**: Shows current schedule state (idle, running, stopped, error)
- **Execution Tracking**: Displays last run timestamp and next scheduled run time
- **Manual Trigger**: "Run Now" button for testing without waiting for next interval

**Signals:**
- `schedule_enabled_changed(str, bool)`: Emitted when enabling/disabling (script_name, enabled)
- `schedule_interval_changed(str, int)`: Emitted when interval changes (script_name, interval_seconds)
- `run_now_requested(str)`: Emitted when manual execution requested (script_name)

**Signal Blocking:**
- Uses blockSignals() during programmatic updates to prevent cascading signal emissions
- Prevents UI state loops during schedule configuration updates

## GUI Components

### 1. TrayManager (`gui/tray_manager.py`)

The primary user interface component that manages the system tray:
- **System Tray Icon**: Primary interface for user interaction
- **Context Menus**: Dynamic script menus with real-time status updates
- **Script Execution**: Handles script triggering from tray menus
- **Hotkey Integration**: Connects global hotkeys to script execution
- **Notifications**: Shows execution results and system messages
- **Font Support**: Respects user font settings for menu appearance

```python
class TrayManager(QObject):
    def refresh_scripts(self)  # Update available scripts
    def refresh_hotkeys(self)  # Update hotkey registrations
    def execute_script_by_name(self, script_name: str)  # Execute via hotkey
    def show_notification(self, title: str, message: str)  # User feedback
```

### 2. MainWindow (`gui/main_window.py`)

Minimal window that serves as parent for dialogs and settings:
- **Hidden by Default**: Not shown to user, exists only for dialog parenting
- **Settings Coordination**: Manages settings dialog and preference changes
- **Script Loading**: Coordinates script discovery and loading
- **Hotkey Management**: Integrates hotkey system with tray manager
- **Single Instance**: Ensures only one application instance runs

### 3. HotkeyConfigurator (`gui/hotkey_configurator.py`)

GUI components for hotkey configuration:

#### HotkeyRecorder Widget
- **Key Capture**: Real-time key combination recording
- **Visual Feedback**: Shows current key combination as typed
- **Validation**: Prevents invalid combinations and provides feedback
- **Modifier Support**: Ctrl, Alt, Shift, Win key combinations

#### HotkeyConfigDialog
- **Script Selection**: Configure hotkeys for specific scripts
- **Conflict Detection**: Prevents duplicate or system-reserved hotkeys
- **Clear Functionality**: Remove existing hotkey assignments

### 4. SettingsDialog (`gui/settings_dialog.py`)

Enhanced settings interface supporting:
- **Hotkey Configuration**: Tabbed interface for hotkey management
- **Script Settings**: Configuration for script behavior
- **Application Preferences**: Font settings, startup options, notifications
- **Real-time Validation**: Immediate feedback on setting changes

## Script System

### Dual Script Architecture

The application supports two types of scripts with different lifecycles:

#### 1. Legacy UtilityScript Scripts

1. **Discovery Phase**
   ```
   ScriptLoader.discover_scripts()
   ├── Scan scripts/ directory
   ├── Filter *.py files
   ├── Exclude __*.py files
   └── Try to import and find UtilityScript subclasses
   ```

2. **Loading Phase** 
   ```
   ScriptLoader._load_script(path)
   ├── Import module
   ├── Find UtilityScript subclasses
   ├── Instantiate class
   └── Call validate()
   ```

3. **Execution Phase**
   ```
   User Interaction (Tray/Hotkey)
   ├── TrayManager.execute_script()
   ├── Call script.execute()
   └── Show result notification
   ```

#### 2. Standalone Scripts

1. **Analysis Phase**
   ```
   ScriptAnalyzer.analyze_script(path)
   ├── Parse Python AST
   ├── Detect main function or __main__ block
   ├── Extract argparse or function arguments
   └── Determine execution strategy
   ```

2. **Execution Phase**
   ```
   User Interaction (Tray/Hotkey/CLI)
   ├── ScriptExecutor.execute_script()
   ├── Apply execution strategy:
   │   ├── SUBPROCESS: Run with args
   │   ├── FUNCTION_CALL: Import & call
   │   └── MODULE_EXEC: Import & execute
   └── Return ExecutionResult
   ```

### Script Implementation Example

```python
class CustomScript(UtilityScript):
    def get_metadata(self):
        return {
            'name': 'My Script',
            'description': 'Does something useful',
            'button_type': ButtonType.TOGGLE,
            'button_options': ToggleOptions(
                on_label="Enabled",
                off_label="Disabled"
            )
        }
    
    def get_status(self):
        # Return current state without side effects
        return self._check_current_state()
    
    def execute(self, enabled):
        # Perform the action
        if self._perform_action(enabled):
            return {
                'success': True,
                'message': f'State changed to {enabled}'
            }
        return {
            'success': False,
            'message': 'Failed to change state'
        }
    
    def validate(self):
        # Check system compatibility
        return sys.platform == 'win32'
```

## Communication Flow

### Script Menu Update Flow
```
Periodic Updates (5-second timer):
TrayManager.refresh_scripts()
├── ScriptLoader.discover_scripts()
├── For each script:
│   ├── Get current status
│   └── Update tray menu text
└── Refresh tray context menu
```

### Tray Menu Execution Flow
```
User clicks script in tray menu:
TrayManager → Script execution
├── Identify script type (Legacy/Standalone)
├── Execute appropriate handler:
│   ├── Legacy: script.execute()
│   └── Standalone: ScriptExecutor.execute_script()
├── Capture result
├── Show notification with result
└── Update script status in menu
```

### Global Hotkey Execution Flow
```
Windows hotkey pressed:
Win32 WM_HOTKEY message → HotkeyWidget.nativeEvent()
├── HotkeyWidget.hotkey_triggered(hotkey_id)
├── HotkeyManager._on_hotkey_triggered(hotkey_id)
├── Map hotkey_id to script_name
├── HotkeyManager.hotkey_triggered.emit(script_name, hotkey_string)
├── TrayManager.execute_script_by_name(script_name)
├── Execute script (same as tray menu flow)
└── Show notification with result
```

### Settings & Hotkey Configuration Flow
```
User configures hotkey:
SettingsDialog → Hotkeys Tab
├── User selects script and clicks hotkey cell
├── HotkeyConfigDialog opens
├── HotkeyRecorder captures key combination
├── Validate hotkey (conflicts, system reserved)
├── HotkeyRegistry.add_hotkey(script, hotkey)
├── Save to QSettings (Windows Registry)
├── MainWindow.hotkeys_changed signal
├── TrayManager.refresh_hotkeys()
└── HotkeyManager.register_hotkey() with Windows API
```

## Error Handling

### Three Levels of Error Isolation

1. **Script Loading Errors**
   - Caught by ScriptLoader
   - Script excluded from loaded list
   - Error logged to failed_scripts dict
   - Application continues with other scripts

2. **Script Execution Errors**
   - Caught by ScriptExecutor thread
   - Error signal emitted
   - Error displayed in UI
   - Widget re-enabled for retry

3. **Status Update Errors**
   - Caught in update_status()
   - Error displayed in status label
   - Next update attempted after 5 seconds

### Error Recovery Strategies

- **Graceful Degradation**: Show error in UI, don't crash
- **User Notification**: QMessageBox for critical errors
- **Logging**: All errors logged with context
- **Retry Logic**: User can retry failed operations
- **Hot Reload**: Refresh button to reload problematic scripts

## Logging System

### Logger Hierarchy
```
Root Logger
├── MAIN (Application lifecycle)
├── GUI.MainWindow (Window events)
├── GUI.ScriptWidget (Widget interactions)
├── GUI.ButtonFactory (Button creation)
└── Core.ScriptLoader (Script discovery)
```

### Log Levels and Usage

| Level | Usage | Example |
|-------|-------|---------|
| DEBUG | Detailed flow information | "Creating widget for script: Display Mode" |
| INFO | Important events | "Successfully loaded 3 script(s)" |
| WARNING | Non-critical issues | "Script not available on this system" |
| ERROR | Failures with recovery | "Error loading script: file.py" |

### Log Format
```
HH:MM:SS | LEVEL    | MODULE.Class         | Message
10:59:35 | INFO     | GUI.MainWindow       | Loading scripts...
```

## Performance Considerations

1. **Tray-Only Architecture**: No main window UI reduces memory footprint and startup time
2. **Single Instance**: Shared memory prevents multiple app instances and resource conflicts
3. **AST Analysis Caching**: Script analysis results cached to avoid repeated parsing
4. **Lazy Script Loading**: Scripts analyzed only when first accessed or during discovery
5. **Efficient Hotkey Handling**: Native Windows API with minimal Qt widget overhead
6. **Subprocess Optimization**: `CREATE_NO_WINDOW` flag prevents console popups
7. **Status Update Batching**: Tray menu updates batched with 5-second timer
8. **Font Setting Caching**: Font configurations cached and applied efficiently

## Security Considerations

1. **Script Isolation**: Both legacy and standalone scripts isolated from main application
2. **AST Analysis Only**: Script analysis uses safe AST parsing, never executes code
3. **Subprocess Safety**: All subprocess calls use `shell=False` and `CREATE_NO_WINDOW`
4. **Hotkey Validation**: System-reserved hotkeys blocked to prevent security conflicts
5. **Single Instance**: Prevents multiple instances and potential security holes
6. **Settings Storage**: Hotkeys stored in user registry space (not system-wide)
7. **No Network Access**: Core application has no network dependencies
8. **Execution Timeouts**: Scripts have configurable timeout limits to prevent hanging

## Future Enhancements

### Planned Features
- **Cross-Platform Hotkeys**: Linux and macOS hotkey support
- **Script Scheduling**: Cron-like scheduling for automated script execution
- **Script Chaining**: Multi-script workflows and dependencies
- **Cloud Sync**: Hotkey and script configuration synchronization
- **Script Store**: Built-in marketplace for sharing community scripts
- **Advanced Analysis**: Enhanced AST analysis for better argument detection
- **Performance Monitoring**: Script execution time tracking and optimization
- **Script Templates**: Code generation templates for common script patterns

### Extension Points
- **Hotkey Providers**: Pluggable hotkey backends for different platforms
- **Execution Strategies**: Additional script execution methods (containers, sandboxes)
- **Analysis Plugins**: Custom AST analyzers for specific script patterns
- **Notification Backends**: Alternative notification systems (toast, desktop, email)
- **Settings Backends**: Alternative storage systems (cloud, file-based)
- **Theme System**: Complete UI customization and theming support
- **Script Metadata**: Enhanced metadata fields and validation
- **Internationalization**: Multi-language support throughout the application
