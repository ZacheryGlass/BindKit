import sys
import os
import logging
import winreg
from pathlib import Path
from typing import Optional

logger = logging.getLogger('Core.StartupManager')

class StartupManager:
    APP_NAME = "BindKit"
    
    def __init__(self):
        self.startup_key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        self.executable_path = self._get_executable_path()
        logger.info(f"StartupManager initialized with executable: {self.executable_path}")
    
    def _get_executable_path(self) -> str:
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            return sys.executable
        else:
            # Running as Python script
            main_script = Path(__file__).parent.parent / "main.py"
            return f'"{sys.executable}" "{main_script.absolute()}"'
    
    def is_registered(self) -> bool:
        if sys.platform != 'win32':
            return False
        
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.startup_key_path, 0, winreg.KEY_READ) as key:
                try:
                    value, _ = winreg.QueryValueEx(key, self.APP_NAME)
                    logger.debug(f"Startup registry value found: {value}")
                    return True
                except FileNotFoundError:
                    return False
        except Exception as e:
            logger.error(f"Error checking startup registration: {e}")
            return False
    
    def register(self) -> bool:
        if sys.platform != 'win32':
            logger.warning("Startup registration only supported on Windows")
            return False
        
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.startup_key_path, 0, winreg.KEY_WRITE) as key:
                # Add --minimized flag to start in tray
                startup_command = f'{self.executable_path} --minimized'
                winreg.SetValueEx(key, self.APP_NAME, 0, winreg.REG_SZ, startup_command)
                logger.info(f"Successfully registered for startup: {startup_command}")
                return True
        except Exception as e:
            logger.error(f"Failed to register for startup: {e}")
            return False
    
    def unregister(self) -> bool:
        if sys.platform != 'win32':
            return False
        
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.startup_key_path, 0, winreg.KEY_WRITE) as key:
                try:
                    winreg.DeleteValue(key, self.APP_NAME)
                    logger.info("Successfully removed from startup")
                    return True
                except FileNotFoundError:
                    logger.info("Not registered for startup (entry not found)")
                    return True
        except Exception as e:
            logger.error(f"Failed to remove from startup: {e}")
            return False
    
    def set_startup(self, enabled: bool) -> bool:
        if enabled:
            return self.register()
        else:
            return self.unregister()
    
    def get_registered_command(self) -> Optional[str]:
        if sys.platform != 'win32':
            return None
        
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.startup_key_path, 0, winreg.KEY_READ) as key:
                try:
                    value, _ = winreg.QueryValueEx(key, self.APP_NAME)
                    return value
                except FileNotFoundError:
                    return None
        except Exception as e:
            logger.error(f"Error reading startup command: {e}")
            return None
    
    def update_path_if_needed(self) -> bool:
        if not self.is_registered():
            return True
        
        current_command = self.get_registered_command()
        expected_command = f'{self.executable_path} --minimized'
        
        if current_command != expected_command:
            logger.info(f"Updating startup path from '{current_command}' to '{expected_command}'")
            return self.register()
        
        return True