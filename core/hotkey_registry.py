import logging
import threading
from typing import Dict, List, Optional, Tuple
from PyQt6.QtCore import QObject, pyqtSignal
from core.settings import SettingsManager
from core.script_loader import ScriptLoader

logger = logging.getLogger('Core.HotkeyRegistry')


class HotkeyRegistry(QObject):
    """
    Manages persistent storage and validation of hotkey-to-script mappings
    """
    
    hotkey_added = pyqtSignal(str, str)  # script_name, hotkey_string
    hotkey_removed = pyqtSignal(str)  # script_name
    hotkey_updated = pyqtSignal(str, str, str)  # script_name, old_hotkey, new_hotkey
    
    def __init__(self, settings_manager: Optional[SettingsManager] = None):
        super().__init__()
        self.settings = settings_manager or SettingsManager()
        self._mappings: Dict[str, str] = {}  # script_name -> hotkey_string
        self._reverse_mappings: Dict[str, str] = {}  # hotkey_string -> script_name
        self._lock = threading.RLock()
        
        # Load existing mappings from settings
        self._load_mappings()
        
        logger.info(f"HotkeyRegistry initialized with {len(self._mappings)} mappings")
    
    def _load_mappings(self):
        """Load hotkey mappings from settings"""
        with self._lock:
            self._mappings.clear()
            self._reverse_mappings.clear()
            
            # Get all hotkey settings
            settings = self.settings.settings
            settings.beginGroup("hotkeys")
            
            for script_name in settings.childKeys():
                hotkey_string = settings.value(script_name)
                if hotkey_string:
                    self._mappings[script_name] = hotkey_string
                    self._reverse_mappings[hotkey_string] = script_name
                    logger.debug(f"Loaded hotkey mapping: {script_name} -> {hotkey_string}")
            
            settings.endGroup()
    
    def _save_mapping(self, script_name: str, hotkey_string: Optional[str]):
        """Save a single hotkey mapping to settings"""
        key = f"hotkeys/{script_name}"
        
        if hotkey_string:
            self.settings.set(key, hotkey_string)
        else:
            # Remove the setting if hotkey is None/empty
            self.settings.settings.remove(key)
        
        self.settings.sync()
    
    def add_hotkey(self, script_name: str, hotkey_string: str) -> Tuple[bool, str]:
        """
        Add or update a hotkey mapping
        
        Returns: (success, error_message)
        """
        if not script_name or not hotkey_string:
            return False, "Script name and hotkey cannot be empty"
        
        # Normalize the hotkey string
        normalized_hotkey = hotkey_string.strip()
        
        with self._lock:
            # Check if hotkey is already assigned to another script
            existing_script = self._reverse_mappings.get(normalized_hotkey)
            if existing_script and existing_script != script_name:
                return False, f"Hotkey {normalized_hotkey} is already assigned to {existing_script}"
            
            # Check if script already has a different hotkey
            old_hotkey = self._mappings.get(script_name)
            
            # Update mappings
            self._mappings[script_name] = normalized_hotkey
            self._reverse_mappings[normalized_hotkey] = script_name
            
            # Remove old reverse mapping if it exists
            if old_hotkey and old_hotkey != normalized_hotkey:
                self._reverse_mappings.pop(old_hotkey, None)
            
            # Save to settings while still holding the lock to prevent interleaving writes
            self._save_mapping(script_name, normalized_hotkey)
        
        # Emit appropriate signal outside the lock to avoid deadlocks
        if old_hotkey and old_hotkey != normalized_hotkey:
            logger.info(f"Updated hotkey for {script_name}: {old_hotkey} -> {normalized_hotkey}")
            self.hotkey_updated.emit(script_name, old_hotkey, normalized_hotkey)
        else:
            logger.info(f"Added hotkey for {script_name}: {normalized_hotkey}")
            self.hotkey_added.emit(script_name, normalized_hotkey)
        
        return True, ""
    
    def remove_hotkey(self, script_name: str) -> bool:
        """
        Remove a hotkey mapping for a script
        
        Returns: True if a hotkey was removed, False if no hotkey existed
        """
        with self._lock:
            if script_name not in self._mappings:
                logger.debug(f"No hotkey mapping found for {script_name}")
                return False
            
            hotkey_string = self._mappings[script_name]
            
            # Remove from mappings
            del self._mappings[script_name]
            self._reverse_mappings.pop(hotkey_string, None)
            
            # Remove from settings
            self._save_mapping(script_name, None)
        
        logger.info(f"Removed hotkey for {script_name}: {hotkey_string}")
        self.hotkey_removed.emit(script_name)
        
        return True
    
    def get_hotkey(self, script_name: str) -> Optional[str]:
        """Get the hotkey string for a script"""
        with self._lock:
            return self._mappings.get(script_name)
    
    def get_hotkey_for_script(self, script_name: str) -> Optional[str]:
        """Backwards-compatible alias for get_hotkey."""
        return self.get_hotkey(script_name)
    
    def get_script_for_hotkey(self, hotkey_string: str) -> Optional[str]:
        """Get the script name for a hotkey string"""
        with self._lock:
            return self._reverse_mappings.get(hotkey_string)
    
    def get_all_mappings(self) -> Dict[str, str]:
        """Get all hotkey mappings as a dictionary"""
        with self._lock:
            return self._mappings.copy()
    
    def get_scripts_with_hotkeys(self) -> List[str]:
        """Get a list of all scripts that have hotkeys assigned"""
        with self._lock:
            return list(self._mappings.keys())
    
    def has_hotkey(self, script_name: str) -> bool:
        """Check if a script has a hotkey assigned"""
        with self._lock:
            return script_name in self._mappings
    
    def is_hotkey_assigned(self, hotkey_string: str) -> bool:
        """Check if a hotkey string is already assigned to any script"""
        with self._lock:
            return hotkey_string in self._reverse_mappings
    
    def clear_all(self):
        """Remove all hotkey mappings"""
        scripts = self.get_scripts_with_hotkeys()
        for script_name in scripts:
            self.remove_hotkey(script_name)
        
        logger.info("Cleared all hotkey mappings")
    
    def validate_mappings(self, script_loader: ScriptLoader) -> List[str]:
        """
        Validate all mappings against available scripts
        Remove orphaned mappings and return list of removed script names
        """
        removed = []
        available_scripts = set()
        
        # Get names of all available scripts
        for script in script_loader.discover_scripts():
            try:
                metadata = script.get_metadata()
                script_name = metadata.get('name', '')
                if script_name:
                    available_scripts.add(script_name)
            except Exception as e:
                logger.error(f"Error getting script metadata: {e}")
        
        # Snapshot current mappings to avoid locking while discovering scripts
        with self._lock:
            current_mappings = list(self._mappings.keys())

        # Check each mapping
        for script_name in current_mappings:
            if script_name not in available_scripts:
                logger.warning(f"Removing orphaned hotkey for non-existent script: {script_name}")
                self.remove_hotkey(script_name)
                removed.append(script_name)
        
        if removed:
            logger.info(f"Removed {len(removed)} orphaned hotkey mappings")
        
        return removed
    
    def export_mappings(self) -> Dict[str, str]:
        """Export all mappings for backup/sharing"""
        return self.get_all_mappings()
    
    def import_mappings(self, mappings: Dict[str, str], overwrite: bool = False) -> Tuple[int, List[str]]:
        """
        Import hotkey mappings
        
        Args:
            mappings: Dictionary of script_name -> hotkey_string
            overwrite: If True, overwrite existing mappings
        
        Returns: (number_imported, list_of_conflicts)
        """
        imported = 0
        conflicts = []
        
        for script_name, hotkey_string in mappings.items():
            if not overwrite and self.has_hotkey(script_name):
                conflicts.append(f"{script_name} already has hotkey {self._mappings[script_name]}")
                continue
            
            success, error = self.add_hotkey(script_name, hotkey_string)
            if success:
                imported += 1
            else:
                conflicts.append(f"{script_name}: {error}")
        
        logger.info(f"Imported {imported} hotkey mappings, {len(conflicts)} conflicts")
        
        return imported, conflicts
    
    def get_hotkey_conflicts(self, hotkey_string: str, exclude_script: Optional[str] = None) -> Optional[str]:
        """
        Check if a hotkey would conflict with existing mappings
        
        Args:
            hotkey_string: The hotkey to check
            exclude_script: Script name to exclude from conflict check (for updates)
        
        Returns: Name of conflicting script or None
        """
        with self._lock:
            existing_script = self._reverse_mappings.get(hotkey_string)
        
        if existing_script and existing_script != exclude_script:
            return existing_script
        
        return None
