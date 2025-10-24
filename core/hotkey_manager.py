import logging
from typing import Dict, Optional, Tuple, Set
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication, QWidget
import win32con
import win32api
import win32gui

logger = logging.getLogger('Core.HotkeyManager')

# Windows modifier key constants
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000  # Prevents repeat when held down

# Virtual key code mappings
VK_CODES = {
    'F1': win32con.VK_F1, 'F2': win32con.VK_F2, 'F3': win32con.VK_F3,
    'F4': win32con.VK_F4, 'F5': win32con.VK_F5, 'F6': win32con.VK_F6,
    'F7': win32con.VK_F7, 'F8': win32con.VK_F8, 'F9': win32con.VK_F9,
    'F10': win32con.VK_F10, 'F11': win32con.VK_F11, 'F12': win32con.VK_F12,
    '0': ord('0'), '1': ord('1'), '2': ord('2'), '3': ord('3'), '4': ord('4'),
    '5': ord('5'), '6': ord('6'), '7': ord('7'), '8': ord('8'), '9': ord('9'),
    'A': ord('A'), 'B': ord('B'), 'C': ord('C'), 'D': ord('D'), 'E': ord('E'),
    'F': ord('F'), 'G': ord('G'), 'H': ord('H'), 'I': ord('I'), 'J': ord('J'),
    'K': ord('K'), 'L': ord('L'), 'M': ord('M'), 'N': ord('N'), 'O': ord('O'),
    'P': ord('P'), 'Q': ord('Q'), 'R': ord('R'), 'S': ord('S'), 'T': ord('T'),
    'U': ord('U'), 'V': ord('V'), 'W': ord('W'), 'X': ord('X'), 'Y': ord('Y'),
    'Z': ord('Z'),
    'SPACE': win32con.VK_SPACE, 'ENTER': win32con.VK_RETURN,
    'TAB': win32con.VK_TAB, 'ESCAPE': win32con.VK_ESCAPE, 'ESC': win32con.VK_ESCAPE,
    'BACKSPACE': win32con.VK_BACK, 'DELETE': win32con.VK_DELETE,
    'INSERT': win32con.VK_INSERT, 'HOME': win32con.VK_HOME,
    'END': win32con.VK_END, 'PAGEUP': win32con.VK_PRIOR,
    'PAGEDOWN': win32con.VK_NEXT, 'UP': win32con.VK_UP,
    'DOWN': win32con.VK_DOWN, 'LEFT': win32con.VK_LEFT,
    'RIGHT': win32con.VK_RIGHT,
    'NUMPAD0': win32con.VK_NUMPAD0, 'NUMPAD1': win32con.VK_NUMPAD1,
    'NUMPAD2': win32con.VK_NUMPAD2, 'NUMPAD3': win32con.VK_NUMPAD3,
    'NUMPAD4': win32con.VK_NUMPAD4, 'NUMPAD5': win32con.VK_NUMPAD5,
    'NUMPAD6': win32con.VK_NUMPAD6, 'NUMPAD7': win32con.VK_NUMPAD7,
    'NUMPAD8': win32con.VK_NUMPAD8, 'NUMPAD9': win32con.VK_NUMPAD9,
    'MULTIPLY': win32con.VK_MULTIPLY, 'ADD': win32con.VK_ADD,
    'SUBTRACT': win32con.VK_SUBTRACT, 'DIVIDE': win32con.VK_DIVIDE,
    'DECIMAL': win32con.VK_DECIMAL,
    'PAUSE': win32con.VK_PAUSE, 'CAPSLOCK': win32con.VK_CAPITAL,
    'NUMLOCK': win32con.VK_NUMLOCK, 'SCROLLLOCK': win32con.VK_SCROLL,
    'PRINTSCREEN': win32con.VK_SNAPSHOT,
    'PLUS': 0xBB, 'MINUS': 0xBD,  # OEM Plus and Minus keys
    'COMMA': 0xBC, 'PERIOD': 0xBE,  # OEM Comma and Period
    'SLASH': 0xBF, 'BACKSLASH': 0xDC,  # OEM 2 and 5
    'SEMICOLON': 0xBA, 'QUOTE': 0xDE,  # OEM 1 and 7
    'BRACKET_LEFT': 0xDB, 'BRACKET_RIGHT': 0xDD,  # OEM 4 and 6
    'GRAVE': 0xC0,  # OEM 3
}

# Reverse mapping for display
VK_NAMES = {v: k for k, v in VK_CODES.items()}

# System-reserved hotkey combinations to block
RESERVED_HOTKEYS = {
    ('CTRL', 'C'), ('CTRL', 'V'), ('CTRL', 'X'), ('CTRL', 'A'),
    ('CTRL', 'Z'), ('CTRL', 'Y'), ('CTRL', 'S'), ('CTRL', 'O'),
    ('CTRL', 'N'), ('CTRL', 'P'), ('CTRL', 'F'), ('CTRL', 'H'),
    ('ALT', 'TAB'), ('ALT', 'F4'), ('ALT', 'ESCAPE'),
    ('CTRL', 'ALT', 'DELETE'), ('CTRL', 'SHIFT', 'ESCAPE'),
    ('WIN', 'L'), ('WIN', 'D'), ('WIN', 'E'), ('WIN', 'R'),
    ('WIN', 'TAB'), ('WIN', 'X'),
}


class HotkeyWidget(QWidget):
    """Hidden Qt widget that receives Windows hotkey messages in the main thread"""
    hotkey_triggered = pyqtSignal(int)  # Emits hotkey ID when triggered
    
    def __init__(self):
        super().__init__()
        self.hwnd = None
        
        try:
            # Set window flags to make it invisible and not interfere with other windows
            from PyQt6.QtCore import Qt
            self.setWindowFlags(
                Qt.WindowType.Tool | 
                Qt.WindowType.FramelessWindowHint | 
                Qt.WindowType.WindowStaysOnBottomHint
            )
            
            # Hide the widget and make it very small
            self.hide()
            self.resize(1, 1)
            
            # Ensure the widget is created and get the window handle
            logger.debug("Creating hotkey widget window handle...")
            self.show()  # Briefly show to create the window
            
            # Get window ID and verify it's valid
            win_id = self.winId()
            if win_id == 0:
                raise RuntimeError("Failed to create widget window - winId() returned 0")
            
            self.hwnd = int(win_id)
            self.hide()  # Hide it again
            
            if self.hwnd <= 0:
                raise RuntimeError(f"Invalid window handle: {self.hwnd}")
            
            logger.info(f"Hotkey widget created successfully with hwnd: {self.hwnd}")
            
        except Exception as e:
            logger.error(f"Failed to create HotkeyWidget: {e}")
            self.hwnd = None
            raise
    
    def nativeEvent(self, eventType, message):
        """Handle native Windows events"""
        try:
            if eventType == "windows_generic_MSG":
                import ctypes
                from ctypes import wintypes
                
                # Cast the message to a MSG structure
                msg = ctypes.cast(int(message), ctypes.POINTER(wintypes.MSG)).contents
                
                if msg.message == win32con.WM_HOTKEY:
                    hotkey_id = msg.wParam
                    logger.debug(f"Hotkey triggered via nativeEvent: ID {hotkey_id}")
                    self.hotkey_triggered.emit(hotkey_id)
                    return True, 0
                    
        except Exception as e:
            logger.error(f"Error handling native event: {e}")
        
        return False, 0


class HotkeyManager(QObject):
    """Manages global hotkey registration and handling"""
    
    hotkey_triggered = pyqtSignal(str, str)  # script_name, hotkey_string
    registration_failed = pyqtSignal(str, str, str)  # script_name, hotkey_string, error_message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.widget = None
        self.hotkeys: Dict[int, Tuple[str, str]] = {}  # ID -> (script_name, hotkey_string)
        self.registered_combos: Set[str] = set()  # Track registered combinations
        self.next_id = 1
        
        logger.info("HotkeyManager initialized")
    
    def start(self):
        """Start the hotkey system by creating the widget in main thread"""
        if self.widget is None:
            try:
                logger.info("Starting HotkeyManager - creating HotkeyWidget...")
                self.widget = HotkeyWidget()
                
                # Verify widget was created successfully
                if not hasattr(self.widget, 'hwnd') or not self.widget.hwnd:
                    logger.error("HotkeyWidget failed to create window handle")
                    # Clean up partially created widget
                    if self.widget:
                        try:
                            self.widget.hide()
                            self.widget.deleteLater()
                        except (RuntimeError, AttributeError) as e:
                            logger.debug(f"Could not clean up partially created widget: {e}")
                    self.widget = None
                    return False
                
                self.widget.hotkey_triggered.connect(self._on_hotkey_triggered)
                logger.info(f"HotkeyManager started successfully with widget HWND: {self.widget.hwnd}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start HotkeyManager: {e}")
                # Clean up any partially created widget
                if self.widget:
                    try:
                        self.widget.hide()
                        self.widget.deleteLater()
                    except (RuntimeError, AttributeError) as e:
                        logger.debug(f"Could not clean up widget after error: {e}")
                self.widget = None
                return False
        else:
            logger.debug("HotkeyManager already started")
            return True
    
    def stop(self):
        """Stop the hotkey system and unregister all hotkeys"""
        logger.info("Stopping HotkeyManager...")
        
        # Unregister all hotkeys first
        self.unregister_all()
        
        # Additional safety cleanup for orphaned hotkeys
        self._cleanup_orphaned_hotkeys()
        
        # Clean up widget
        if self.widget:
            try:
                # Disconnect signal to prevent issues during cleanup
                self.widget.hotkey_triggered.disconnect()
            except (TypeError, RuntimeError) as e:
                logger.debug(f"Hotkey widget signal already disconnected or not connected: {e}")

            # Explicitly destroy the native window to free Windows resources
            try:
                self.widget.hide()
                self.widget.close()  # Close the window
                self.widget.destroy()  # Destroy the native window handle
            except (RuntimeError, AttributeError) as e:
                logger.debug(f"Error destroying widget window: {e}")

            self.widget.deleteLater()
            self.widget = None
        
        logger.info("HotkeyManager stopped")
    
    def parse_hotkey_string(self, hotkey_string: str) -> Tuple[int, int]:
        """
        Parse a hotkey string like 'Ctrl+Alt+X' into modifier flags and virtual key code
        
        Returns: (modifiers, vk_code) or (0, 0) if invalid
        """
        parts = [p.strip().upper() for p in hotkey_string.upper().split('+')]
        
        if not parts:
            return 0, 0
        
        modifiers = 0
        key = None
        
        for part in parts:
            if part in ('CTRL', 'CONTROL'):
                modifiers |= MOD_CONTROL
            elif part == 'ALT':
                modifiers |= MOD_ALT
            elif part == 'SHIFT':
                modifiers |= MOD_SHIFT
            elif part in ('WIN', 'WINDOWS', 'SUPER'):
                modifiers |= MOD_WIN
            else:
                # This should be the actual key
                if key is None:
                    key = part
                else:
                    # Multiple non-modifier keys - invalid
                    logger.warning(f"Invalid hotkey string: {hotkey_string}")
                    return 0, 0
        
        if key is None:
            logger.warning(f"No key specified in hotkey string: {hotkey_string}")
            return 0, 0
        
        # Get virtual key code
        vk_code = VK_CODES.get(key, 0)
        if vk_code == 0:
            # Try single character
            if len(key) == 1:
                vk_code = ord(key)
            else:
                logger.warning(f"Unknown key: {key}")
                return 0, 0
        
        # Add no-repeat flag to prevent key repeat
        modifiers |= MOD_NOREPEAT
        
        return modifiers, vk_code
    
    def is_hotkey_available(self, hotkey_string: str) -> bool:
        """Check if a hotkey combination is available for registration"""
        normalized = self.normalize_hotkey_string(hotkey_string)
        
        # Check if already registered
        if normalized in self.registered_combos:
            return False
        
        # Check if it's a reserved combination
        if self.is_reserved_hotkey(hotkey_string):
            return False
        
        return True
    
    def is_reserved_hotkey(self, hotkey_string: str) -> bool:
        """Check if a hotkey combination is system-reserved"""
        parts = set(p.strip().upper() for p in hotkey_string.upper().split('+'))
        
        # Remove modifier duplicates and normalize
        normalized_parts = set()
        for part in parts:
            if part in ('CTRL', 'CONTROL'):
                normalized_parts.add('CTRL')
            elif part in ('WIN', 'WINDOWS', 'SUPER'):
                normalized_parts.add('WIN')
            else:
                normalized_parts.add(part)
        
        # Check against reserved combinations
        for reserved in RESERVED_HOTKEYS:
            if set(reserved) == normalized_parts:
                return True

        return False

    def _validate_widget_handle(self) -> bool:
        """
        Validate that the widget window handle is still valid.

        Returns:
            True if handle is valid, False otherwise
        """
        if not self.widget or not hasattr(self.widget, 'hwnd') or not self.widget.hwnd:
            logger.warning("Widget or window handle is not initialized")
            return False

        try:
            # Verify the widget's winId is still valid
            win_id = self.widget.winId()
            if win_id == 0 or int(win_id) != self.widget.hwnd:
                logger.error(f"Widget window handle has become invalid (was {self.widget.hwnd}, now {win_id})")
                return False

            return True
        except (RuntimeError, AttributeError) as e:
            logger.error(f"Error validating widget handle: {e}")
            return False

    def normalize_hotkey_string(self, hotkey_string: str) -> str:
        """Normalize a hotkey string for consistent comparison"""
        parts = []
        hotkey_upper = hotkey_string.upper()
        
        # Extract modifiers in consistent order
        if 'CTRL' in hotkey_upper or 'CONTROL' in hotkey_upper:
            parts.append('Ctrl')
        if 'ALT' in hotkey_upper:
            parts.append('Alt')
        if 'SHIFT' in hotkey_upper:
            parts.append('Shift')
        if 'WIN' in hotkey_upper or 'WINDOWS' in hotkey_upper or 'SUPER' in hotkey_upper:
            parts.append('Win')
        
        # Extract the main key
        for part in hotkey_string.split('+'):
            part = part.strip()
            part_upper = part.upper()
            if part_upper not in ('CTRL', 'CONTROL', 'ALT', 'SHIFT', 'WIN', 'WINDOWS', 'SUPER'):
                parts.append(part_upper)
                break
        
        return '+'.join(parts)
    
    def register_hotkey(self, script_name: str, hotkey_string: str) -> bool:
        """
        Register a global hotkey for a script
        
        Returns: True if successful, False otherwise
        """
        if not self.widget:
            logger.error("Hotkey system not started")
            return False
        
        # Normalize the hotkey string
        normalized = self.normalize_hotkey_string(hotkey_string)
        
        # Check if available
        if not self.is_hotkey_available(normalized):
            error_msg = f"Hotkey {normalized} is already registered or reserved"
            logger.warning(error_msg)
            self.registration_failed.emit(script_name, normalized, error_msg)
            return False
        
        # Parse the hotkey string
        modifiers, vk_code = self.parse_hotkey_string(hotkey_string)
        if modifiers == 0 and vk_code == 0:
            error_msg = f"Invalid hotkey format: {hotkey_string}"
            logger.error(error_msg)
            self.registration_failed.emit(script_name, hotkey_string, error_msg)
            return False
        
        # Validate widget and window handle are still valid
        if not self._validate_widget_handle():
            error_msg = "Hotkey system not started or widget handle invalid"
            logger.error(error_msg)
            self.registration_failed.emit(script_name, normalized, error_msg)
            return False
            
        hotkey_id = self.next_id
        self.next_id += 1
        
        # Attempt to register with Windows using the widget's HWND
        try:
            # RegisterHotKey returns 0 on failure, non-zero on success (Windows API convention)
            result = win32gui.RegisterHotKey(
                self.widget.hwnd, hotkey_id, modifiers, vk_code
            )

            if result == 0:
                # Registration failed - retrieve error code for diagnostics
                import win32api
                error_code = win32api.GetLastError()
                if error_code == 1409:  # ERROR_HOTKEY_ALREADY_REGISTERED
                    error_msg = f"Hotkey {normalized} is already registered by another application"
                else:
                    error_msg = f"Failed to register hotkey {normalized}: Windows error {error_code}"
                logger.error(error_msg)
                self.registration_failed.emit(script_name, normalized, error_msg)
                return False

            # Validate that we got a valid success code
            logger.debug(f"RegisterHotKey returned {result} for hotkey {normalized}")
            
            # Registration successful
            self.hotkeys[hotkey_id] = (script_name, normalized)
            self.registered_combos.add(normalized)
            logger.info(f"Registered hotkey {normalized} for script {script_name} (ID: {hotkey_id})")
            return True
                
        except Exception as e:
            error_msg = f"Exception registering hotkey {normalized}: {str(e)}"
            logger.error(error_msg)
            self.registration_failed.emit(script_name, normalized, error_msg)
            return False
    
    def unregister_hotkey(self, script_name: str) -> bool:
        """Unregister a hotkey for a script"""
        if not self.widget:
            return False
        
        # Find the hotkey ID for this script
        hotkey_id = None
        hotkey_string = None
        
        for hid, (sname, hstring) in self.hotkeys.items():
            if sname == script_name:
                hotkey_id = hid
                hotkey_string = hstring
                break
        
        if hotkey_id is None:
            logger.warning(f"No hotkey registered for script {script_name}")
            return False
        
        # Unregister with Windows
        try:
            win32gui.UnregisterHotKey(self.widget.hwnd, hotkey_id)
            
            # If we get here, unregistration was successful
            del self.hotkeys[hotkey_id]
            self.registered_combos.discard(hotkey_string)
            logger.info(f"Unregistered hotkey for script {script_name}")
            return True
                
        except Exception as e:
            logger.error(f"Exception unregistering hotkey for {script_name}: {e}")
            return False
    
    def unregister_all(self):
        """Unregister all hotkeys"""
        if not self.widget:
            return
        
        for hotkey_id in list(self.hotkeys.keys()):
            try:
                win32gui.UnregisterHotKey(self.widget.hwnd, hotkey_id)
            except Exception as e:
                logger.error(f"Error unregistering hotkey {hotkey_id}: {e}")
        
        self.hotkeys.clear()
        self.registered_combos.clear()
        logger.info("All hotkeys unregistered")
    
    def get_registered_hotkeys(self) -> Dict[str, str]:
        """
        Get all registered hotkeys as script_name -> hotkey_string mapping.

        Note: self.hotkeys is structured as {hotkey_id: (script_name, hotkey_string)},
        so .values() gives us tuples of (script_name, hotkey_string) which we unpack
        in the dict comprehension to create the desired {script_name: hotkey_string} mapping.
        """
        return {script_name: hotkey_string
                for script_name, hotkey_string in self.hotkeys.values()}
    
    def _on_hotkey_triggered(self, hotkey_id: int):
        """Handle hotkey trigger from widget"""
        if hotkey_id in self.hotkeys:
            script_name, hotkey_string = self.hotkeys[hotkey_id]
            logger.info(f"Hotkey {hotkey_string} triggered for script {script_name}")
            self.hotkey_triggered.emit(script_name, hotkey_string)
        else:
            logger.warning(f"Unknown hotkey ID triggered: {hotkey_id}")
    
    def validate_hotkey_string(self, hotkey_string: str) -> Tuple[bool, str]:
        """
        Validate a hotkey string
        
        Returns: (is_valid, error_message)
        """
        if not hotkey_string or not hotkey_string.strip():
            return False, "Hotkey cannot be empty"
        
        # Check format
        modifiers, vk_code = self.parse_hotkey_string(hotkey_string)
        if modifiers == 0 and vk_code == 0:
            return False, "Invalid hotkey format"
        
        # Check if reserved
        if self.is_reserved_hotkey(hotkey_string):
            return False, "This hotkey combination is reserved by the system"
        
        # Check if already registered
        normalized = self.normalize_hotkey_string(hotkey_string)
        if normalized in self.registered_combos:
            return False, "This hotkey is already registered"
        
        return True, ""
    
    def validate_registration_status(self) -> Dict[str, Dict[str, any]]:
        """
        Validate that all registered hotkeys are actually working with Windows
        
        Returns: Dict mapping script_name to status info:
        {
            'script_name': {
                'hotkey': 'Ctrl+Alt+X',
                'registered': True/False,
                'error': 'error message if any'
            }
        }
        """
        status_info = {}
        
        if not self.widget or not self.widget.hwnd:
            # If widget is not available, all hotkeys are effectively broken
            for script_name, hotkey_string in self.get_registered_hotkeys().items():
                status_info[script_name] = {
                    'hotkey': hotkey_string,
                    'registered': False,
                    'error': 'Hotkey widget not available'
                }
            return status_info
        
        # Check each registered hotkey
        for script_name, hotkey_string in self.get_registered_hotkeys().items():
            try:
                # Parse the hotkey to get modifiers and vk_code
                modifiers, vk_code = self.parse_hotkey_string(hotkey_string)
                
                if modifiers == 0 and vk_code == 0:
                    status_info[script_name] = {
                        'hotkey': hotkey_string,
                        'registered': False,
                        'error': 'Invalid hotkey format'
                    }
                    continue
                
                # Try to register the hotkey temporarily to see if it's available
                # We use a high ID number to avoid conflicts with our actual hotkeys
                test_id = 99999
                try:
                    result = win32gui.RegisterHotKey(
                        self.widget.hwnd, test_id, modifiers, vk_code
                    )
                    
                    if result == 0:
                        # Registration failed - hotkey is likely taken by another app
                        import win32api
                        error_code = win32api.GetLastError()
                        if error_code == 1409:  # ERROR_HOTKEY_ALREADY_REGISTERED
                            error_msg = "Hotkey is registered by another application"
                        else:
                            error_msg = f"Windows error {error_code}"
                        
                        status_info[script_name] = {
                            'hotkey': hotkey_string,
                            'registered': False,
                            'error': error_msg
                        }
                    else:
                        # Registration succeeded, so the hotkey should be available
                        # Immediately unregister our test
                        win32gui.UnregisterHotKey(self.widget.hwnd, test_id)
                        
                        status_info[script_name] = {
                            'hotkey': hotkey_string,
                            'registered': True,
                            'error': None
                        }
                        
                except Exception as e:
                    status_info[script_name] = {
                        'hotkey': hotkey_string,
                        'registered': False,
                        'error': f'Validation failed: {str(e)}'
                    }
                    
            except Exception as e:
                status_info[script_name] = {
                    'hotkey': hotkey_string,
                    'registered': False,
                    'error': f'Error validating hotkey: {str(e)}'
                }
        
        return status_info
    
    def _cleanup_orphaned_hotkeys(self):
        """
        Cleanup any orphaned hotkey registrations that might exist.
        
        This method attempts to unregister hotkeys using a range of IDs
        that might have been registered by previous instances or failed cleanup.
        """
        if not self.widget or not self.widget.hwnd:
            return
            
        logger.debug("Cleaning up orphaned hotkey registrations...")
        
        # Try to unregister hotkeys in a reasonable range
        # This covers hotkeys that might have been registered by previous runs
        cleanup_count = 0
        for hotkey_id in range(1, 100):  # Reasonable range for cleanup
            try:
                result = win32gui.UnregisterHotKey(self.widget.hwnd, hotkey_id)
                if result != 0:  # Success
                    cleanup_count += 1
                    logger.debug(f"Cleaned up orphaned hotkey ID: {hotkey_id}")
            except Exception:
                # Ignore errors for non-existent hotkeys
                pass
        
        if cleanup_count > 0:
            logger.info(f"Cleaned up {cleanup_count} orphaned hotkey registrations")
        else:
            logger.debug("No orphaned hotkey registrations found")