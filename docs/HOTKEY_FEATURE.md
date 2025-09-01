# Global Hotkey Feature

## Overview
BindKit now supports global keyboard hotkeys that allow you to execute scripts directly from anywhere in Windows, without needing to open the system tray menu.

## How to Configure Hotkeys

1. **Open Settings**
   - Right-click the system tray icon
   - Select "Settings..."

2. **Navigate to Hotkeys Tab**
   - Click on the "Hotkeys" tab in the settings dialog
   - You'll see a table listing all available scripts

3. **Set a Hotkey**
   - Click on the hotkey cell (shows "(empty)" if no hotkey is set)
   - A recording dialog will appear
   - Press your desired key combination (e.g., Ctrl+Alt+X)
   - The combination will appear in real-time
   - Click "OK" to confirm or "Cancel" to abort

4. **Clear a Hotkey**
   - Click the "Clear" button in the Actions column
   - Or click the hotkey cell and press "Clear Hotkey" in the dialog

## Supported Key Combinations

### Modifiers (at least one required)
- **Ctrl** (Control key)
- **Alt** (Alt key)
- **Shift** (Shift key)
- **Win** (Windows key)

### Main Keys
- Letters: A-Z
- Numbers: 0-9
- Function keys: F1-F12
- Special keys: Space, Enter, Tab, Escape, etc.
- Arrow keys: Up, Down, Left, Right
- Other: Home, End, PageUp, PageDown, Insert, Delete

## Important Notes

### Reserved Combinations
The following combinations are reserved by Windows and cannot be used:
- Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+A (clipboard operations)
- Ctrl+Z, Ctrl+Y (undo/redo)
- Ctrl+S, Ctrl+O, Ctrl+N, Ctrl+P (file operations)
- Alt+Tab, Alt+F4 (window management)
- Win+L, Win+D, Win+E, Win+R (Windows shortcuts)
- Ctrl+Alt+Delete, Ctrl+Shift+Escape (system functions)

### Conflict Detection
- The system will prevent you from assigning the same hotkey to multiple scripts
- If a hotkey is already used by another application, registration will fail with a notification

### Script Types and Hotkeys
- **RUN scripts**: Execute immediately when hotkey is pressed
- **TOGGLE scripts**: Toggle state when hotkey is pressed
- **CYCLE scripts**: Cycle to next option when hotkey is pressed
- **NUMBER/TEXT scripts**: Use default values when triggered via hotkey

## Testing Your Hotkey

A test script is included (`Test Hotkey`) that you can use to verify hotkey functionality:
1. Assign a hotkey to "Test Hotkey" script
2. Press the hotkey combination from anywhere in Windows
3. Check your Desktop for a file named `hotkey_test_executed.txt` confirming execution

## Troubleshooting

### Hotkey Not Working
- Ensure the application is running in the system tray
- Check if another application has already registered the same hotkey
- Try a different combination with more modifiers (e.g., Ctrl+Shift+Alt+X)
- Check notifications for any registration errors

### Application Won't Start
- Ensure PyQt6 and pywin32 are installed: `pip install -r requirements.txt`
- Run with `python main.py --minimized` for tray-only mode

### Settings Not Saving
- Hotkey mappings are stored in Windows Registry
- Ensure you have appropriate permissions
- Click "Apply" or "OK" to save changes

## Technical Details

### Architecture
- **HotkeyManager**: Handles Windows API hotkey registration (RegisterHotKey/UnregisterHotKey)
- **HotkeyRegistry**: Manages persistent storage of hotkey mappings in QSettings
- **HotkeyConfigurator**: GUI widget for recording key combinations
- **Message Loop**: Dedicated thread listening for WM_HOTKEY messages

### Storage
Hotkey mappings are stored in the Windows Registry at:
`HKEY_CURRENT_USER\Software\DesktopUtils\DesktopUtilityGUI\hotkeys\`

### Edge Cases Handled
- Script deletion: Orphaned hotkeys are automatically cleaned up
- Script failures: Notifications show error messages
- Duplicate hotkeys: Prevented at configuration time
- Application restart: Hotkeys are re-registered on startup
- Multiple instances: Only primary instance registers hotkeys
