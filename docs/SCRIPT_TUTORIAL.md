# Tutorial: Creating Custom Utility Scripts

This tutorial covers creating scripts for BindKit using both legacy UtilityScript classes and modern standalone scripts with global hotkey support.

## Table of Contents
1. [Quick Start](#quick-start)
2. [Script Types Overview](#script-types-overview)
3. [Legacy UtilityScript Examples](#legacy-utilityscript-examples)
4. [Standalone Script Examples](#standalone-script-examples)
5. [Global Hotkey Configuration](#global-hotkey-configuration)
6. [Scheduled Script Execution](#scheduled-script-execution)
7. [Advanced Techniques](#advanced-techniques)
8. [Best Practices](#best-practices)
9. [Troubleshooting](#troubleshooting)

## Quick Start

### Legacy UtilityScript Template

Create a new Python file in the `scripts/` directory:

```python
import sys
sys.path.append('..')  # Required for imports

from core.base_script import UtilityScript
from core.button_types import ButtonType

class MyScript(UtilityScript):
    def get_metadata(self):
        return {
            'name': 'My Script',
            'description': 'Does something useful',
            'button_type': ButtonType.RUN
        }
    
    def get_status(self):
        return "Ready"
    
    def execute(self):
        # Your code here
        return {'success': True, 'message': 'Done!'}
    
    def validate(self):
        return True  # Available on all systems
```

### Standalone Script Template

Create a modern standalone script:

```python
#!/usr/bin/env python3
"""
Simple standalone script example.
Can be executed via tray menu, hotkeys, or command line.
"""
import json
import sys

def main():
    """Main function"""
    result = {
        'success': True,
        'message': 'Standalone script executed successfully!'
    }
    
    # Output JSON for the application to parse
    print(json.dumps(result))
    return 0 if result['success'] else 1

if __name__ == '__main__':
    sys.exit(main())
```

Save either template as `scripts/my_script.py` and it will appear in the system tray menu automatically!

## Script Types Overview

The application supports two types of scripts with different capabilities:

### Legacy UtilityScript (Class-based)

**Best for:** Complex UI interactions, stateful scripts, real-time status updates

**Features:**
- Rich button types (TOGGLE, CYCLE, SLIDER, etc.)
- Real-time status display in tray menus
- Built-in validation and error handling
- Full PyQt6 integration

**Execution:** Via tray menu or global hotkeys

### Standalone Scripts (Function-based)

**Best for:** Command-line tools, system utilities, simple automations

**Features:**
- AST-based analysis for automatic argument detection
- Multiple execution strategies (subprocess, function call, module)
- Command-line compatibility
- JSON-based result communication
- Support for argparse integration

**Execution:** Via tray menu, global hotkeys, or direct command line

### Comparison Table

| Feature | Legacy UtilityScript | Standalone Scripts |
|---------|--------------------|--------------------|
| **Complexity** | Higher (class structure) | Lower (simple functions) |
| **UI Types** | All button types | Basic execution |
| **Status Updates** | Real-time via get_status() | Static display name |
| **Arguments** | Via execute() parameters | Via argparse or function parameters |
| **Command Line** | Not directly executable | Fully command-line compatible |
| **Validation** | Built-in validate() method | Automatic compatibility checking |
| **Global Hotkeys** | ✅ Supported | ✅ Supported |
| **Error Handling** | Manual via return dict | Automatic via subprocess/exceptions |

## Legacy UtilityScript Examples

### The Four Required Methods

Every script must implement these four methods:

1. **`get_metadata()`** - Defines how your script appears in the GUI
2. **`get_status()`** - Returns current state (called every 5 seconds)
3. **`execute()`** - Performs the actual action
4. **`validate()`** - Checks if script can run on this system

### Button Types and Their Use Cases

| Button Type | Use When You Want To | Example Scripts |
|------------|---------------------|-----------------|
| `RUN` | Execute a one-time action | Clear cache, restart service |
| `TOGGLE` | Switch between two states | WiFi on/off, dark mode |
| `CYCLE` | Rotate through multiple options | Power plans, display modes |
| `SLIDER` | Adjust a numeric value | Volume, brightness |
| `SELECT` | Choose from a dropdown | Language, theme selection |
| `NUMBER` | Input a specific number | Port number, timeout value |
| `TEXT_INPUT` | Enter text | Quick note, search query |

## Step-by-Step Examples

### Example 1: Simple Run Button - Clear Temp Files

```python
import sys
import os
import shutil
from typing import Dict, Any

sys.path.append('..')
from core.base_script import UtilityScript
from core.button_types import ButtonType

class ClearTempFiles(UtilityScript):
    def get_metadata(self) -> Dict[str, Any]:
        return {
            'name': 'Clear Temp Files',
            'description': 'Remove temporary files from system',
            'button_type': ButtonType.RUN
        }
    
    def get_status(self) -> str:
        # Count temp files
        temp_dir = os.environ.get('TEMP', '')
        if os.path.exists(temp_dir):
            file_count = len(os.listdir(temp_dir))
            return f"{file_count} temp files"
        return "Ready"
    
    def execute(self) -> Dict[str, Any]:
        try:
            temp_dir = os.environ.get('TEMP', '')
            if not os.path.exists(temp_dir):
                return {'success': False, 'message': 'Temp directory not found'}
            
            # Count files before deletion
            files_before = len(os.listdir(temp_dir))
            deleted = 0
            
            # Delete temp files
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                    deleted += 1
                except Exception:
                    pass  # Skip files in use
            
            return {
                'success': True,
                'message': f'Deleted {deleted} of {files_before} temp files'
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def validate(self) -> bool:
        # Works on any system with TEMP environment variable
        return 'TEMP' in os.environ
```

### Example 2: Toggle Button - WiFi Control

```python
import sys
import subprocess
from typing import Dict, Any

sys.path.append('..')
from core.base_script import UtilityScript
from core.button_types import ButtonType, ToggleOptions

class WiFiToggle(UtilityScript):
    def get_metadata(self) -> Dict[str, Any]:
        return {
            'name': 'WiFi Control',
            'description': 'Enable or disable WiFi adapter',
            'button_type': ButtonType.TOGGLE,
            'button_options': ToggleOptions(
                on_label="Connected",
                off_label="Disconnected",
                show_status=True
            )
        }
    
    def get_status(self) -> bool:
        """Check if WiFi is enabled."""
        if sys.platform != 'win32':
            return False
        
        try:
            result = subprocess.run(
                ['netsh', 'interface', 'show', 'interface'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Look for WiFi adapter status
            for line in result.stdout.split('\n'):
                if 'wi-fi' in line.lower():
                    return 'connected' in line.lower() or 'enabled' in line.lower()
            
            return False
        except Exception:
            return False
    
    def execute(self, enabled: bool) -> Dict[str, Any]:
        """Enable or disable WiFi."""
        try:
            action = 'enable' if enabled else 'disable'
            
            result = subprocess.run(
                ['netsh', 'interface', 'set', 'interface', 'Wi-Fi', action],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': f'WiFi {"enabled" if enabled else "disabled"}'
                }
            else:
                return {
                    'success': False,
                    'message': f'Failed to {action} WiFi: {result.stderr}'
                }
                
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def validate(self) -> bool:
        """Check if we can control WiFi on this system."""
        if sys.platform != 'win32':
            return False
        
        try:
            # Check if netsh is available
            result = subprocess.run(
                ['netsh', '/?'],
                capture_output=True,
                timeout=2,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except Exception:
            return False
```

### Example 3: Cycle Button - Screen Resolution

```python
import sys
import subprocess
from typing import Dict, Any, List

sys.path.append('..')
from core.base_script import UtilityScript
from core.button_types import ButtonType, CycleOptions

class ResolutionCycle(UtilityScript):
    def __init__(self):
        super().__init__()
        self.resolutions = ['1920x1080', '1680x1050', '1280x720']
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            'name': 'Screen Resolution',
            'description': 'Cycle through common resolutions',
            'button_type': ButtonType.CYCLE,
            'button_options': CycleOptions(
                options=self.resolutions,
                show_current=True
            )
        }
    
    def get_status(self) -> str:
        """Get current resolution."""
        try:
            if sys.platform == 'win32':
                # Use PowerShell to get resolution
                cmd = '''
                Add-Type @"
                using System;
                using System.Runtime.InteropServices;
                public class Screen {
                    [DllImport("user32.dll")]
                    public static extern int GetSystemMetrics(int nIndex);
                    public static string GetResolution() {
                        int width = GetSystemMetrics(0);
                        int height = GetSystemMetrics(1);
                        return width + "x" + height;
                    }
                }
"@
                [Screen]::GetResolution()
                '''
                
                result = subprocess.run(
                    ['powershell', '-Command', cmd],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0:
                    resolution = result.stdout.strip()
                    if resolution in self.resolutions:
                        return resolution
            
            return self.resolutions[0]  # Default
            
        except Exception:
            return self.resolutions[0]
    
    def execute(self, resolution: str) -> Dict[str, Any]:
        """Change screen resolution."""
        try:
            if resolution not in self.resolutions:
                return {'success': False, 'message': 'Invalid resolution'}
            
            width, height = resolution.split('x')
            
            # PowerShell script to change resolution
            cmd = f'''
            $pinvoke = @"
            using System;
            using System.Runtime.InteropServices;
            public class Display {{
                [DllImport("user32.dll")]
                public static extern int ChangeDisplaySettings(ref DEVMODE devMode, int flags);
                
                [StructLayout(LayoutKind.Sequential)]
                public struct DEVMODE {{
                    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
                    public string dmDeviceName;
                    public short dmSpecVersion;
                    public short dmDriverVersion;
                    public short dmSize;
                    public short dmDriverExtra;
                    public int dmFields;
                    public int dmPositionX;
                    public int dmPositionY;
                    public int dmDisplayOrientation;
                    public int dmDisplayFixedOutput;
                    public short dmColor;
                    public short dmDuplex;
                    public short dmYResolution;
                    public short dmTTOption;
                    public short dmCollate;
                    [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
                    public string dmFormName;
                    public short dmLogPixels;
                    public int dmBitsPerPel;
                    public int dmPelsWidth;
                    public int dmPelsHeight;
                    public int dmDisplayFlags;
                    public int dmDisplayFrequency;
                }}
            }}
"@
            Add-Type $pinvoke
            
            $devMode = New-Object Display+DEVMODE
            $devMode.dmSize = [System.Runtime.InteropServices.Marshal]::SizeOf($devMode)
            $devMode.dmPelsWidth = {width}
            $devMode.dmPelsHeight = {height}
            $devMode.dmFields = 0x80000 -bor 0x100000
            
            [Display]::ChangeDisplaySettings([ref]$devMode, 0)
            '''
            
            result = subprocess.run(
                ['powershell', '-Command', cmd],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': f'Resolution changed to {resolution}'
                }
            else:
                return {'success': False, 'message': 'Failed to change resolution'}
                
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def validate(self) -> bool:
        return sys.platform == 'win32'
```

### Example 4: Slider - CPU Priority

```python
import sys
import os
import psutil  # You'll need to pip install psutil
from typing import Dict, Any

sys.path.append('..')
from core.base_script import UtilityScript
from core.button_types import ButtonType, SliderOptions

class CPUPriority(UtilityScript):
    def __init__(self):
        super().__init__()
        self.priority_map = {
            20: 'Idle',
            40: 'Below Normal',
            60: 'Normal',
            80: 'Above Normal',
            100: 'High'
        }
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            'name': 'Process Priority',
            'description': 'Adjust current process CPU priority',
            'button_type': ButtonType.SLIDER,
            'button_options': SliderOptions(
                min_value=20,
                max_value=100,
                step=20,
                show_value=True,
                suffix=""
            )
        }
    
    def get_status(self) -> int:
        """Get current process priority as slider value."""
        try:
            process = psutil.Process(os.getpid())
            nice = process.nice()
            
            # Map nice values to slider values
            if sys.platform == 'win32':
                nice_map = {
                    psutil.IDLE_PRIORITY_CLASS: 20,
                    psutil.BELOW_NORMAL_PRIORITY_CLASS: 40,
                    psutil.NORMAL_PRIORITY_CLASS: 60,
                    psutil.ABOVE_NORMAL_PRIORITY_CLASS: 80,
                    psutil.HIGH_PRIORITY_CLASS: 100
                }
                return nice_map.get(nice, 60)
            
            return 60  # Default to normal
            
        except Exception:
            return 60
    
    def execute(self, value: float) -> Dict[str, Any]:
        """Set process priority based on slider value."""
        try:
            value = int(value)
            priority_name = self.priority_map.get(value, 'Normal')
            
            process = psutil.Process(os.getpid())
            
            if sys.platform == 'win32':
                priority_map = {
                    20: psutil.IDLE_PRIORITY_CLASS,
                    40: psutil.BELOW_NORMAL_PRIORITY_CLASS,
                    60: psutil.NORMAL_PRIORITY_CLASS,
                    80: psutil.ABOVE_NORMAL_PRIORITY_CLASS,
                    100: psutil.HIGH_PRIORITY_CLASS
                }
                
                priority = priority_map.get(value, psutil.NORMAL_PRIORITY_CLASS)
                process.nice(priority)
            else:
                # Unix nice values (-20 to 19)
                nice_map = {20: 19, 40: 10, 60: 0, 80: -10, 100: -20}
                nice_value = nice_map.get(value, 0)
                process.nice(nice_value)
            
            return {
                'success': True,
                'message': f'Priority set to {priority_name}'
            }
            
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def validate(self) -> bool:
        try:
            import psutil
            return True
        except ImportError:
            return False
```

### Example 5: Text Input - Quick Note

```python
import sys
import os
from datetime import datetime
from typing import Dict, Any

sys.path.append('..')
from core.base_script import UtilityScript
from core.button_types import ButtonType, TextInputOptions

class QuickNote(UtilityScript):
    def __init__(self):
        super().__init__()
        self.notes_dir = os.path.expanduser("~/Desktop/QuickNotes")
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            'name': 'Quick Note',
            'description': 'Save a quick note to desktop',
            'button_type': ButtonType.TEXT_INPUT,
            'button_options': TextInputOptions(
                placeholder="Type your note here...",
                max_length=500,
                multiline=False
            )
        }
    
    def get_status(self) -> str:
        """Show how many notes exist."""
        if os.path.exists(self.notes_dir):
            note_count = len([f for f in os.listdir(self.notes_dir) 
                            if f.endswith('.txt')])
            return f"{note_count} notes saved"
        return "No notes yet"
    
    def execute(self, note_text: str) -> Dict[str, Any]:
        """Save the note to a file."""
        try:
            if not note_text.strip():
                return {'success': False, 'message': 'Note is empty'}
            
            # Create notes directory if it doesn't exist
            os.makedirs(self.notes_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"note_{timestamp}.txt"
            filepath = os.path.join(self.notes_dir, filename)
            
            # Write note to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Quick Note - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("-" * 40 + "\n")
                f.write(note_text)
            
            return {
                'success': True,
                'message': f'Note saved to {filename}'
            }
            
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def validate(self) -> bool:
        # Works on any system
        return True
```

## Advanced Techniques

### Using External Libraries

```python
# Install required package: pip install requests
import sys
import requests

sys.path.append('..')
from core.base_script import UtilityScript
from core.button_types import ButtonType

class WeatherCheck(UtilityScript):
    def get_metadata(self):
        return {
            'name': 'Weather Check',
            'description': 'Get current weather',
            'button_type': ButtonType.RUN
        }
    
    def get_status(self):
        return "Click to check weather"
    
    def execute(self):
        try:
            # Use a weather API
            response = requests.get('https://wttr.in/?format=%C+%t')
            if response.status_code == 200:
                weather = response.text.strip()
                return {'success': True, 'message': f'Current weather: {weather}'}
            else:
                return {'success': False, 'message': 'Failed to get weather'}
        except Exception as e:
            return {'success': False, 'message': str(e)}
    
    def validate(self):
        try:
            import requests
            return True
        except ImportError:
            return False  # requests not installed
```

### Storing State Between Executions

```python
import sys
import json
import os
from typing import Dict, Any

sys.path.append('..')
from core.base_script import UtilityScript
from core.button_types import ButtonType

class Counter(UtilityScript):
    def __init__(self):
        super().__init__()
        self.state_file = os.path.expanduser("~/.counter_state.json")
        self.load_state()
    
    def load_state(self):
        """Load saved state from file."""
        try:
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
        except Exception:
            self.state = {'count': 0}
    
    def save_state(self):
        """Save state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f)
        except Exception:
            pass
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            'name': 'Click Counter',
            'description': 'Counts button clicks',
            'button_type': ButtonType.RUN
        }
    
    def get_status(self) -> str:
        return f"Count: {self.state['count']}"
    
    def execute(self) -> Dict[str, Any]:
        self.state['count'] += 1
        self.save_state()
        return {
            'success': True,
            'message': f"Count increased to {self.state['count']}"
        }
    
    def validate(self) -> bool:
        return True
```

### Async Operations with Progress

```python
import sys
import time
import threading
from typing import Dict, Any

sys.path.append('..')
from core.base_script import UtilityScript
from core.button_types import ButtonType

class LongOperation(UtilityScript):
    def __init__(self):
        super().__init__()
        self.progress = 0
        self.running = False
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            'name': 'Long Operation',
            'description': 'Simulates a long-running task',
            'button_type': ButtonType.RUN
        }
    
    def get_status(self) -> str:
        if self.running:
            return f"Running... {self.progress}%"
        return "Ready"
    
    def execute(self) -> Dict[str, Any]:
        if self.running:
            return {'success': False, 'message': 'Already running'}
        
        # Note: The actual execution happens in a thread via ScriptExecutor
        # This method should complete the operation before returning
        
        self.running = True
        self.progress = 0
        
        try:
            # Simulate long operation
            for i in range(10):
                time.sleep(1)  # Simulate work
                self.progress = (i + 1) * 10
            
            self.running = False
            self.progress = 100
            
            return {'success': True, 'message': 'Operation completed!'}
            
        except Exception as e:
            self.running = False
            return {'success': False, 'message': str(e)}
    
    def validate(self) -> bool:
        return True
```

## Best Practices

### 1. Error Handling

Always wrap operations in try-except blocks:

```python
def execute(self):
    try:
        # Your operation
        result = perform_operation()
        return {'success': True, 'message': 'Success'}
    except SpecificError as e:
        # Handle specific errors
        return {'success': False, 'message': f'Specific error: {e}'}
    except Exception as e:
        # Catch-all for unexpected errors
        return {'success': False, 'message': f'Unexpected error: {e}'}
```

### 2. Status Updates

Keep status messages informative but concise:

```python
def get_status(self):
    # Good: Informative
    return f"CPU: {cpu_usage}%, RAM: {ram_usage}%"
    
    # Bad: Too verbose
    return f"The current CPU usage is {cpu_usage} percent and memory is {ram_usage} percent"
    
    # Bad: Not informative
    return "OK"
```

### 3. Validation

Check all requirements in validate():

```python
def validate(self):
    # Check OS
    if sys.platform != 'win32':
        return False
    
    # Check required commands
    try:
        subprocess.run(['required_command', '--version'], 
                      capture_output=True, timeout=1)
    except Exception:
        return False
    
    # Check permissions
    if not os.access('/required/path', os.W_OK):
        return False
    
    # Check dependencies
    try:
        import required_module
    except ImportError:
        return False
    
    return True
```

### 4. Subprocess Best Practices

Always use these flags for subprocess on Windows:

```python
result = subprocess.run(
    ['command', 'args'],
    capture_output=True,        # Capture stdout/stderr
    text=True,                   # Return strings, not bytes
    timeout=10,                  # Prevent hanging
    creationflags=subprocess.CREATE_NO_WINDOW  # No console popup
)
```

### 5. Logging for Debugging

Use the logging system for debugging:

```python
import logging

class MyScript(UtilityScript):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(f'Script.{self.__class__.__name__}')
    
    def execute(self):
        self.logger.debug("Starting execution")
        try:
            result = perform_operation()
            self.logger.info(f"Operation successful: {result}")
            return {'success': True}
        except Exception as e:
            self.logger.error(f"Operation failed: {e}", exc_info=True)
            return {'success': False}
```

## Troubleshooting

### Common Issues and Solutions

#### Script Not Appearing in GUI

1. **Check filename**: Must end with `.py` and not start with `__`
2. **Check imports**: Ensure `sys.path.append('..')` is at the top
3. **Check class**: Must inherit from `UtilityScript`
4. **Check validation**: `validate()` must return `True`
5. **Check syntax**: Run `python scripts/your_script.py` to check for errors

#### Script Crashes GUI

This shouldn't happen due to error isolation, but if it does:

1. Check for infinite loops in `get_status()`
2. Ensure `get_status()` is lightweight (no heavy operations)
3. Check for import errors at module level
4. Verify all required methods are implemented

#### Button Not Working

1. Check execute method signature matches button type:
   - Toggle: `execute(self, enabled: bool)`
   - Slider: `execute(self, value: float)`
   - Text: `execute(self, text: str)`
2. Check return value is a dict with 'success' key
3. Check logs for error messages

#### Status Not Updating

1. Ensure `get_status()` returns quickly (under 1 second)
2. Check return type matches button type
3. Look for exceptions in console output

### Debug Mode

Enable debug logging to see detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Testing Your Script

Test your script standalone before adding to GUI:

```python
if __name__ == "__main__":
    # Test your script
    script = MyScript()
    
    # Test metadata
    print("Metadata:", script.get_metadata())
    
    # Test validation
    print("Valid:", script.validate())
    
    # Test status
    print("Status:", script.get_status())
    
    # Test execution
    result = script.execute()
    print("Result:", result)
```

## Standalone Script Examples

Standalone scripts are analyzed using Python's AST (Abstract Syntax Tree) and can be executed via multiple strategies.

### Simple Standalone Script

```python
#!/usr/bin/env python3
"""Simple utility script with no arguments"""
import json
import subprocess
import sys

def main():
    """Clear Windows temp files"""
    try:
        # Get temp directory
        temp_dir = subprocess.run(['echo', '%TEMP%'], shell=True, capture_output=True, text=True)
        temp_path = temp_dir.stdout.strip()
        
        # Count files (simulation)
        result = {
            'success': True,
            'message': f'Cleaned temp files from {temp_path}',
            'data': {'files_removed': 15}
        }
    except Exception as e:
        result = {
            'success': False,
            'message': f'Error: {str(e)}'
        }
    
    # Always output JSON for the GUI to parse
    print(json.dumps(result))
    return 0 if result['success'] else 1

if __name__ == '__main__':
    sys.exit(main())
```

### Argparse-Based Script

```python
#!/usr/bin/env python3
"""Volume control script with command line arguments"""
import argparse
import json
import sys

def set_volume(level):
    """Set system volume level"""
    # Simulated volume setting
    return {
        'success': True,
        'message': f'Volume set to {level}%'
    }

def get_volume():
    """Get current volume level"""
    # Simulated volume getting
    return 75

def main():
    parser = argparse.ArgumentParser(description='Control system volume')
    parser.add_argument('--level', type=int, choices=range(0, 101), metavar='0-100',
                       help='Set volume level (0-100)')
    parser.add_argument('--mute', action='store_true',
                       help='Mute audio')
    parser.add_argument('--unmute', action='store_true', 
                       help='Unmute audio')
    parser.add_argument('--status', action='store_true',
                       help='Show current volume level')
    
    args = parser.parse_args()
    
    try:
        if args.status:
            volume = get_volume()
            result = {
                'success': True,
                'message': f'Current volume: {volume}%',
                'data': {'volume': volume}
            }
        elif args.level is not None:
            result = set_volume(args.level)
        elif args.mute:
            result = {
                'success': True,
                'message': 'Audio muted'
            }
        elif args.unmute:
            result = {
                'success': True,
                'message': 'Audio unmuted'
            }
        else:
            # Default action
            result = {
                'success': True,
                'message': 'Use --help for available options'
            }
    except Exception as e:
        result = {
            'success': False,
            'message': f'Error: {str(e)}'
        }
    
    print(json.dumps(result))
    return 0 if result['success'] else 1

if __name__ == '__main__':
    sys.exit(main())
```

### Function-Based Script (No Args)

```python
#!/usr/bin/env python3
"""Script with main function - called directly by ScriptExecutor"""
import json

def restart_service():
    """Restart a Windows service"""
    # Simulated service restart
    return {
        'success': True,
        'message': 'Service restarted successfully'
    }

def main():
    """Main function called by ScriptExecutor with FUNCTION_CALL strategy"""
    result = restart_service()
    
    # For FUNCTION_CALL strategy, we can return the dict directly
    # or print JSON - both work
    if __name__ == '__main__':
        print(json.dumps(result))
        return 0 if result['success'] else 1
    else:
        return result

if __name__ == '__main__':
    import sys
    sys.exit(main())
```

### Script Execution Strategies

The ScriptAnalyzer determines the best execution strategy:

1. **SUBPROCESS Strategy** - Used when:
   - Script has argparse arguments
   - Script has `if __name__ == "__main__":` block
   - Best for: Command-line tools, external integrations

2. **FUNCTION_CALL Strategy** - Used when:
   - Script has a `main()` function
   - No arguments or simple function parameters
   - Best for: Direct Python function calls, faster execution

3. **MODULE_EXEC Strategy** - Used when:
   - Script has no main function
   - Script has executable code at module level
   - Best for: Simple scripts, imports

### Command Line Compatibility

All standalone scripts can be executed directly:

```bash
# Execute script directly
python scripts/volume_control.py --level 50

# With status check
python scripts/volume_control.py --status

# In automation scripts
if python scripts/service_restart.py; then
    echo "Service restart successful"
fi

# From project root
python scripts/temp_cleaner.py
```

## Global Hotkey Configuration

Scripts can be assigned global hotkey combinations for instant access.

### Setting Up Hotkeys

1. **Access Settings:**
   - Right-click the system tray icon
   - Select "Settings..."
   - Click the "Hotkeys" tab

2. **Assign a Hotkey:**
   - Find your script in the table
   - Click the empty hotkey cell (shows "(empty)")
   - Press your desired key combination (e.g., Ctrl+Alt+X)
   - Click "OK" to confirm

3. **Supported Combinations:**
   - **Modifiers:** Ctrl, Alt, Shift, Win (at least one required)
   - **Keys:** Letters (A-Z), Numbers (0-9), Function keys (F1-F12)
   - **Special Keys:** Space, Enter, Arrow keys, etc.

### Hotkey Examples

```
Ctrl+Alt+V     - Volume Control
Ctrl+Shift+T   - Temp File Cleaner  
Win+Alt+D      - Display Toggle
Ctrl+Alt+F1    - Service Restart
```

### Reserved Combinations

These hotkey combinations are blocked for security:
- System clipboard: Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+A
- File operations: Ctrl+S, Ctrl+O, Ctrl+N, Ctrl+P  
- Window management: Alt+Tab, Alt+F4
- Windows shortcuts: Win+L, Win+D, Win+E, Win+R
- System functions: Ctrl+Alt+Delete, Ctrl+Shift+Escape

### Hotkey Testing

Use the built-in "Test Hotkey" script to verify hotkey functionality:
1. Assign a hotkey to the "Test Hotkey" script
2. Press the hotkey combination from anywhere in Windows
3. Check your Desktop for `hotkey_test_executed.txt` file

### Troubleshooting Hotkeys

**Hotkey not working:**
- Ensure another application isn't using the same combination
- Try a more unique combination (e.g., Ctrl+Shift+Alt+X)
- Check that the application is running in the system tray

**Registration failed:**
- The hotkey may be reserved by another application
- Try a different combination
- Check the notification area for error messages

## Scheduled Script Execution

Scripts can be configured to run automatically at regular intervals using the built-in scheduler. This is useful for periodic tasks like system maintenance, data backups, or status checks.

### Quick Start: Enabling Schedules

1. **Access Schedule Settings:**
   - Right-click the system tray icon
   - Select "Settings..."
   - Click the "Schedule" tab

2. **Configure a Schedule:**
   - Select a script from the list
   - Check "Enable Schedule" to activate scheduling
   - Set the interval: Choose a number and select the unit (seconds, minutes, hours, or days)
   - Click "Run Now" to test the script
   - Click "OK" to save

3. **Monitor Execution:**
   - View "Last run" time to see when the script last executed
   - View "Next run" time to see when it will execute next
   - Check the status display for current execution state

### Interval Configuration

The scheduler supports flexible interval configuration:

**Units:**
- **Seconds**: For rapid execution (minimum 10 seconds)
- **Minutes**: For regular checks (e.g., every 30 minutes)
- **Hours**: For daily maintenance (e.g., every 4 hours)
- **Days**: For long-term operations (e.g., every 1 day)

**Interval Limits:**
- **Minimum**: 10 seconds (prevents excessive system load)
- **Maximum**: ~24.8 days (QTimer 32-bit millisecond limit)

### Overlap Prevention

The scheduler includes automatic overlap prevention to ensure reliable execution:

**What it does:**
- Prevents the same script from running multiple times simultaneously
- If a script is still executing when the next interval arrives, that execution is skipped
- Prevents resource exhaustion and cascading failures

**Implications:**
- If a script takes longer than its interval to complete, some scheduled runs will be skipped
- For example: 5-minute interval with a 7-minute execution = some intervals skipped
- Solution: Increase interval to be longer than typical execution time

**Viewing Overlaps:**
- Blocked executions are logged in the application
- Use "Run Now" to manually test if overlaps are occurring

### Best Practices for Scheduled Scripts

**1. Make Scripts Idempotent**
Scripts should be safe to run multiple times, even if previous runs didn't complete:

```python
#!/usr/bin/env python3
"""Script for periodic system cleanup"""
import json

def main():
    # Good: Safe to run multiple times
    # If the file doesn't exist, the check still succeeds
    try:
        import os
        if os.path.exists('/tmp/temp_file'):
            os.remove('/tmp/temp_file')

        return {
            'success': True,
            'message': 'Cleanup completed'
        }
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }
```

**2. Set Appropriate Timeouts**
Ensure scripts complete within reasonable time:

```python
# Set a timeout for network operations
result = subprocess.run(
    ['command'],
    capture_output=True,
    timeout=30,  # 30 seconds max
    creationflags=subprocess.CREATE_NO_WINDOW
)
```

**3. Return Proper Status**
Always return JSON with success/failure status:

```python
result = {
    'success': True,
    'message': 'Operation completed successfully',
    'data': {'items_processed': 42}
}
print(json.dumps(result))
```

**4. Handle Failures Gracefully**
Scripts should never crash the scheduler:

```python
try:
    # Perform operation
    perform_operation()
    return {'success': True, 'message': 'Done'}
except SpecificError as e:
    # Handle known errors
    return {'success': False, 'message': f'Known issue: {e}'}
except Exception as e:
    # Catch all unexpected errors
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return {'success': False, 'message': 'Unexpected error'}
```

**5. Log Important Events**
Use logging for debugging scheduled execution:

```python
import logging
logger = logging.getLogger(__name__)

def main():
    logger.info("Scheduled execution started")
    try:
        # Perform work
        logger.debug("Processing items...")
        logger.info("Scheduled execution completed")
    except Exception as e:
        logger.error(f"Scheduled execution failed: {e}")
```

### Testing Scheduled Execution

**Using test_scheduled_execution.py:**

The application includes a test script specifically for verifying scheduler functionality:

1. **Configure Schedule:**
   - Open Settings > Schedule tab
   - Select "Test Scheduled Execution"
   - Enable Schedule and set to 1 minute interval
   - Click "Run Now"

2. **Verify Execution:**
   - Check the application directory for `scheduled_execution_test.log`
   - Log file shows each execution with timestamp
   - Timestamps should match your schedule interval

3. **Test Overlap Prevention:**
   - Configure with short interval (30 seconds)
   - Run with delay: `python scripts/test_scheduled_execution.py --delay 60`
   - Some executions will be skipped due to overlap prevention

### Viewing Execution History

**Last Run:**
- Shows the exact time the script last executed
- Format: YYYY-MM-DD HH:MM:SS
- "Never" indicates the script hasn't run yet

**Next Run:**
- Shows when the next execution is scheduled
- Format: YYYY-MM-DD HH:MM:SS
- Updated each time the script executes

### Persistence Across Restarts

All schedule configurations persist across application restarts:

- **Enabled/Disabled State**: Remembered for each script
- **Intervals**: Saved with your settings
- **Execution Times**: Last run and next run timestamps are stored
- **Auto-start**: Previously enabled schedules automatically start on launch

Schedule settings are stored in the application's settings file and survive application crashes.

### Manual Trigger: "Run Now"

Test scheduled scripts without waiting for the next interval:

1. Select a script from the Schedule list
2. Click "Run Now"
3. Script executes immediately (if not already running)
4. Last run time updates immediately

Useful for:
- Testing overlap prevention behavior
- Verifying script works before scheduling
- Forcing immediate execution for urgent tasks

### Troubleshooting Scheduled Execution

**Schedule not running:**
1. Check if schedule is enabled (checkbox should be checked)
2. Verify interval is set (should show a number and unit)
3. Confirm application is running in system tray
4. Check that script itself works (test with "Run Now")
5. Review application logs for error messages

**Script execution failures:**
1. Click "Run Now" to test script immediately
2. Check script returns JSON format: `{"success": true/false, "message": "..."}`
3. Verify script has no unhandled exceptions
4. Check script dependencies are installed
5. Review script logs for error details

**Overlapping executions:**
1. If you see "execution blocked" messages, script is taking longer than interval
2. Solution: Increase interval to be longer than typical execution time
3. Example: For a 2-minute execution, use a 5-minute interval minimum

**Timer not starting:**
1. Check interval is between 10 seconds and ~24.8 days
2. Verify script name exists in script list
3. Check application has write permissions for settings
4. Restart application to clear any stale state

**Settings not persisting:**
1. Ensure application exits cleanly (right-click tray > Exit)
2. Check disk space available
3. Verify application folder is not read-only
4. Check settings file: `%APPDATA%/BindKit/settings.ini` (Windows)

## Next Steps

1. **Start Simple**: Begin with a RUN button script
2. **Test Thoroughly**: Test standalone before GUI integration
3. **Add Features Gradually**: Start basic, then add complexity
4. **Share Your Scripts**: Consider contributing useful scripts back to the project
5. **Request Features**: If you need new button types or features, open an issue

Happy scripting!
