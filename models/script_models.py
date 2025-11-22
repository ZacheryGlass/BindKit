"""
Script Models - Manage script discovery, execution, and state.

These models handle all script-related business logic while remaining
UI-agnostic and providing signals for state changes.
"""
import logging
import threading
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal, QThread

from core.script_loader import ScriptLoader
from core.script_analyzer import ScriptInfo
from core.settings import SettingsManager
from core.hotkey_registry import HotkeyRegistry

logger = logging.getLogger('Models.Scripts')


class ScriptExecutionWorker(QThread):
    """Worker thread for executing scripts asynchronously."""
    
    # Signals
    execution_completed = pyqtSignal(dict)  # result dict
    execution_failed = pyqtSignal(str)  # error message
    
    def __init__(self, script_loader, script_key: str, arguments: Dict[str, Any]):
        super().__init__()
        self.script_loader = script_loader
        self.script_key = script_key
        self.arguments = arguments
        self._is_cancelled = False
    
    def run(self):
        """Execute the script in this thread."""
        try:
            if self._is_cancelled:
                self.execution_failed.emit("Script execution cancelled")
                return
            
            # Execute the script
            result = self.script_loader.execute_script(self.script_key, self.arguments)
            
            if self._is_cancelled:
                self.execution_failed.emit("Script execution cancelled")
                return
            
            self.execution_completed.emit(result)
            
        except Exception as e:
            logger.error(f"Script execution thread error: {str(e)}")
            self.execution_failed.emit(str(e))
    
    def cancel(self):
        """Request cancellation of the script execution."""
        self._is_cancelled = True


class ScriptCollectionModel(QObject):
    """
    Model for managing the collection of available scripts.
    
    Handles script discovery, filtering, and maintains the list
    of available scripts for execution.
    """
    
    # Signals emitted when script collection changes
    scripts_discovered = pyqtSignal(list)  # List[ScriptInfo]
    scripts_filtered = pyqtSignal(list)  # List[ScriptInfo] after filtering
    script_added = pyqtSignal(object)  # ScriptInfo
    script_removed = pyqtSignal(str)  # script name
    script_enabled = pyqtSignal(str)  # script name
    script_disabled = pyqtSignal(str)  # script name
    external_script_added = pyqtSignal(str, str)  # name, path
    external_script_removed = pyqtSignal(str)  # name
    
    def __init__(self, scripts_directory: str = "scripts"):
        super().__init__()
        self._script_loader = ScriptLoader(scripts_directory)
        self._settings = SettingsManager()
        
        self._all_scripts: List[ScriptInfo] = []
        self._available_scripts: List[ScriptInfo] = []
        self._disabled_scripts: Set[str] = set()
        self._external_scripts: Dict[str, str] = {}
        
        logger.info("ScriptCollectionModel initialized")
    
    def discover_scripts(self) -> List[ScriptInfo]:
        """Discover all available scripts"""
        logger.info("Discovering scripts...")
        
        try:
            self._all_scripts = self._script_loader.discover_scripts()
            self.scripts_discovered.emit(self._all_scripts)
            
            # Apply filtering
            self._update_available_scripts()
            
            logger.info(f"Discovered {len(self._all_scripts)} scripts, "
                       f"{len(self._available_scripts)} available after filtering")
            
            return self._available_scripts
        except Exception as e:
            logger.error(f"Error discovering scripts: {e}")
            return []
    
    def refresh_scripts(self) -> List[ScriptInfo]:
        """Refresh the script collection"""
        logger.info("Refreshing scripts...")
        return self.discover_scripts()
    
    def get_all_scripts(self) -> List[ScriptInfo]:
        """Get all discovered scripts (including disabled)"""
        return self._all_scripts.copy()
    
    def get_available_scripts(self) -> List[ScriptInfo]:
        """Get currently available (enabled) scripts"""
        return self._available_scripts.copy()
    
    def get_script_by_name(self, name: str) -> Optional[ScriptInfo]:
        """Get script info by name.

        Accepts the display name, new canonical identifier (name+extension),
        or legacy file stem used by older settings/hotkey mappings.
        """
        # First, try exact display name match
        for script in self._all_scripts:
            if script.display_name == name:
                return script
        
        normalized_name = (name or "").strip().lower()
        if not normalized_name:
            return None

        # Try canonical identifier match
        for script in self._all_scripts:
            identifier = getattr(script, 'identifier', None)
            if identifier and identifier == normalized_name:
                return script

        # Fallback: try file stem match (hotkey/settings use stems)
        for script in self._all_scripts:
            try:
                if script.file_path.stem.lower() == normalized_name:
                    return script
            except Exception:
                pass

        # Final fallback: check legacy aliases if present
        for script in self._all_scripts:
            try:
                legacy_keys = getattr(script, 'legacy_keys', [])
                for legacy in legacy_keys:
                    if legacy.lower() == normalized_name:
                        return script
            except Exception:
                continue
        return None
    
    def is_script_disabled(self, script_name: str) -> bool:
        """Check if a script is disabled"""
        return script_name in self._disabled_scripts
    
    def is_external_script(self, script_name: str) -> bool:
        """Check if a script is external"""
        return script_name in self._external_scripts
    
    def disable_script(self, script_name: str):
        """Disable a native script"""
        script = self.get_script_by_name(script_name)
        if script and not self.is_external_script(script_name):
            self._disabled_scripts.add(script_name)
            self._settings.add_disabled_script(script_name)
            self._update_available_scripts()
            self.script_disabled.emit(script_name)
            logger.info(f"Disabled script: {script_name}")
    
    def enable_script(self, script_name: str):
        """Enable a previously disabled script"""
        if script_name in self._disabled_scripts:
            self._disabled_scripts.remove(script_name)
            self._settings.remove_disabled_script(script_name)
            self._update_available_scripts()
            self.script_enabled.emit(script_name)
            logger.info(f"Enabled script: {script_name}")
    
    def add_external_script(self, script_name: str, script_path: str) -> bool:
        """Add an external script"""
        try:
            # Validate the script path
            if not self._settings.validate_external_script_path(script_path):
                logger.error(f"Invalid external script path: {script_path}")
                return False
            
            # Add to settings
            self._settings.add_external_script(script_name, script_path)
            self._external_scripts[script_name] = script_path
            
            # Refresh scripts to include the new one
            self.refresh_scripts()
            
            self.external_script_added.emit(script_name, script_path)
            logger.info(f"Added external script: {script_name} -> {script_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding external script {script_name}: {e}")
            return False
    
    def remove_external_script(self, script_name: str):
        """Remove an external script"""
        if script_name in self._external_scripts:
            script_path = self._external_scripts[script_name]
            
            # Remove from settings
            self._settings.remove_external_script(script_name)
            del self._external_scripts[script_name]
            
            # Refresh scripts to remove it from the collection
            self.refresh_scripts()
            
            self.external_script_removed.emit(script_name)
            logger.info(f"Removed external script: {script_name} -> {script_path}")
    
    def get_script_display_name(self, script_info: ScriptInfo) -> str:
        """Get display name for a script (may be customized)"""
        return self._script_loader.get_script_display_name(script_info)
    
    def _update_available_scripts(self):
        """Update the list of available scripts based on current filters"""
        # Load current settings
        self._disabled_scripts = set(self._settings.get_disabled_scripts())
        self._external_scripts = self._settings.get_external_scripts()
        
        # Filter scripts
        available = []
        for script_info in self._all_scripts:
            script_name = script_info.display_name
            is_external = script_name in self._external_scripts
            
            # Skip disabled native scripts (external scripts are never "disabled", only removed)
            if not is_external and script_name in self._disabled_scripts:
                continue
            
            # For external scripts, verify the path still exists
            if is_external:
                script_path = self._external_scripts.get(script_name)
                if not self._settings.validate_external_script_path(script_path):
                    continue
            
            available.append(script_info)
        
        self._available_scripts = available
        self.scripts_filtered.emit(self._available_scripts)


class ScriptExecutionModel(QObject):
    """
    Model for managing script execution and tracking execution state.
    
    Handles script execution, tracks results, and maintains execution history.
    """
    
    # Signals emitted during script execution
    script_execution_started = pyqtSignal(str)  # script name
    script_execution_completed = pyqtSignal(str, dict)  # script name, result
    script_execution_failed = pyqtSignal(str, str)  # script name, error
    script_execution_progress = pyqtSignal(str, str)  # script name, status message
    
    def __init__(self, script_collection: ScriptCollectionModel):
        super().__init__()
        self._script_collection = script_collection
        self._script_loader = script_collection._script_loader
        self._settings = SettingsManager()
        
        self._execution_results: Dict[str, Dict[str, Any]] = {}
        self._active_workers: Dict[str, ScriptExecutionWorker] = {}  # Track active execution threads
        self._worker_lock = threading.Lock()  # Protect worker dictionary from race conditions
        
        logger.info("ScriptExecutionModel initialized")
    
    def execute_script(self, script_name: str, arguments: Optional[Dict[str, Any]] = None, async_execution: bool = True) -> bool:
        """Execute a script with optional arguments

        Args:
            script_name: Name of the script to execute
            arguments: Optional arguments for the script
            async_execution: If True, execute in background thread. If False, execute synchronously.
                            Note: FUNCTION_CALL and MODULE_EXEC strategies always execute synchronously
                            on the main thread to allow creation of PyQt6 objects.
        """
        try:
            # Check if script is already running (thread-safe)
            with self._worker_lock:
                if script_name in self._active_workers:
                    logger.warning(f"Script {script_name} is already running")
                    self.script_execution_failed.emit(script_name, "Script is already running")
                    return False

            script_info = self._script_collection.get_script_by_name(script_name)
            if not script_info:
                self.script_execution_failed.emit(script_name, f"Script not found: {script_name}")
                return False

            # Import ExecutionStrategy here to avoid circular imports
            from core.script_analyzer import ExecutionStrategy

            # Force synchronous execution for FUNCTION_CALL and MODULE_EXEC strategies
            # These strategies execute script functions directly and may create PyQt6 objects,
            # which must happen on the main thread
            if script_info.execution_strategy in (ExecutionStrategy.FUNCTION_CALL, ExecutionStrategy.MODULE_EXEC):
                async_execution = False

            logger.info(f"Executing script: {script_name} (async={async_execution})")
            self.script_execution_started.emit(script_name)

            # Determine script key for execution (canonical identifier)
            script_key = getattr(script_info, 'identifier', None)
            if not script_key:
                script_key = script_info.file_path.stem.lower()

            if async_execution:
                # Create and start worker thread
                worker = ScriptExecutionWorker(self._script_loader, script_key, arguments or {})
                
                # Connect signals
                worker.execution_completed.connect(lambda result: self._handle_execution_completed(script_name, result))
                worker.execution_failed.connect(lambda error: self._handle_execution_failed(script_name, error))
                worker.finished.connect(lambda: self._cleanup_worker(script_name))
                
                # Store worker and start execution (thread-safe)
                with self._worker_lock:
                    self._active_workers[script_name] = worker
                worker.start()
                
                return True  # Execution started successfully
            else:
                # Synchronous execution (fallback for compatibility)
                result = self._script_loader.execute_script(script_key, arguments or {})
                
                # Store result
                self._execution_results[script_name] = result
                
                if result.get('success', False):
                    self.script_execution_completed.emit(script_name, result)
                    logger.info(f"Script execution completed: {script_name}")
                else:
                    error_msg = result.get('message', 'Unknown error')
                    self.script_execution_failed.emit(script_name, error_msg)
                    logger.error(f"Script execution failed: {script_name} - {error_msg}")
                
                return result.get('success', False)
            
        except Exception as e:
            error_msg = f"Error executing script {script_name}: {str(e)}"
            logger.error(error_msg)
            self.script_execution_failed.emit(script_name, str(e))
            return False
    
    def cancel_script_execution(self, script_name: str) -> bool:
        """Cancel a running script execution.
        
        Args:
            script_name: Name of the script to cancel
            
        Returns:
            True if cancellation was requested, False if script was not running
        """
        with self._worker_lock:
            if script_name not in self._active_workers:
                return False
            worker = self._active_workers[script_name]
            
        logger.info(f"Cancelling script execution: {script_name}")
        
        # Disconnect signals first to prevent race conditions
        try:
            worker.execution_completed.disconnect()
            worker.execution_failed.disconnect()
            worker.finished.disconnect()
        except Exception:
            pass  # Signals might already be disconnected
        
        # Request cancellation
        worker.cancel()
        
        # Try graceful shutdown first
        worker.quit()
        graceful_exit = worker.wait(2000)  # Wait up to 2 seconds for graceful exit
        
        if graceful_exit:
            # Thread exited gracefully, safe to clean up
            self._cleanup_worker_safe(script_name, worker, terminated=False)
        else:
            # Force termination as last resort
            logger.warning(f"Force terminating script thread: {script_name}")
            worker.terminate()
            force_exit = worker.wait(1000)  # Wait another second after termination
            
            if force_exit:
                # Terminated successfully, but don't call deleteLater on terminated threads
                self._cleanup_worker_safe(script_name, worker, terminated=True)
            else:
                # Thread is completely unresponsive, just remove from tracking
                logger.error(f"Thread completely unresponsive: {script_name}")
                with self._worker_lock:
                    self._active_workers.pop(script_name, None)
        
        self.script_execution_failed.emit(script_name, "Execution cancelled by user")
        return True
    
    def is_script_running(self, script_name: str) -> bool:
        """Check if a script is currently running.
        
        Args:
            script_name: Name of the script to check
            
        Returns:
            True if script is running, False otherwise
        """
        with self._worker_lock:
            return script_name in self._active_workers
    
    def _handle_execution_completed(self, script_name: str, result: Dict[str, Any]):
        """Handle successful script execution completion."""
        self._execution_results[script_name] = result
        self.script_execution_completed.emit(script_name, result)
        logger.info(f"Script execution completed: {script_name}")
    
    def _handle_execution_failed(self, script_name: str, error: str):
        """Handle script execution failure."""
        self.script_execution_failed.emit(script_name, error)
        logger.error(f"Script execution failed: {script_name} - {error}")
    
    def _cleanup_worker(self, script_name: str):
        """Clean up worker thread after completion."""
        with self._worker_lock:
            if script_name in self._active_workers:
                worker = self._active_workers.pop(script_name)
                # Always remove from active workers to prevent stuck status
                # Only call deleteLater on threads that finished normally
                if not worker.isRunning():
                    worker.deleteLater()
                    logger.debug(f"Cleaned up finished worker thread: {script_name}")
                else:
                    # Thread might still be finishing up - schedule cleanup for later
                    logger.debug(f"Worker thread still running during cleanup: {script_name}")
                    worker.deleteLater()  # Qt will handle cleanup when thread finishes
    
    def _cleanup_worker_safe(self, script_name: str, worker: ScriptExecutionWorker, terminated: bool = False):
        """Safely clean up worker thread with proper handling of terminated threads.
        
        Args:
            script_name: Name of the script being cleaned up
            worker: The worker thread to clean up
            terminated: True if the thread was forcibly terminated
        """
        # Remove from active workers first (thread-safe)
        with self._worker_lock:
            self._active_workers.pop(script_name, None)
        
        if terminated:
            # For terminated threads, don't call deleteLater as it can cause issues
            # Just let Python's garbage collector handle it when references are gone
            logger.debug(f"Cleaned up terminated thread: {script_name}")
        else:
            # For normally finished threads, use deleteLater
            worker.deleteLater()
            logger.debug(f"Cleaned up finished thread: {script_name}")
    
    def execute_script_with_preset(self, script_name: str, preset_name: str, async_execution: bool = True) -> bool:
        """Execute a script with a specific preset configuration"""
        try:
            script_info = self._script_collection.get_script_by_name(script_name)
            if not script_info:
                self.script_execution_failed.emit(script_name, f"Script not found: {script_name}")
                return False
            
            # Get script key for settings lookup
            script_key = getattr(script_info, 'identifier', None) or script_info.file_path.stem.lower()
            preset_args = self._settings.get_preset_arguments(script_key, preset_name)
            
            logger.info(f"Executing script {script_name} with preset '{preset_name}': {preset_args}")
            return self.execute_script(script_name, preset_args, async_execution)
            
        except Exception as e:
            error_msg = f"Error executing script {script_name} with preset {preset_name}: {str(e)}"
            logger.error(error_msg)
            self.script_execution_failed.emit(script_name, str(e))
            return False
    
    def get_script_status(self, script_name: str) -> str:
        """Get current status of a script"""
        # Simplified: directly get status without caching
        script_info = self._script_collection.get_script_by_name(script_name)
        if script_info:
            script_key = getattr(script_info, 'identifier', None) or script_info.file_path.stem.lower()
            
            status = self._script_loader.get_script_status(script_key)
            return status or "Ready"
        
        return "Unknown"
    
    def get_last_execution_result(self, script_name: str) -> Optional[Dict[str, Any]]:
        """Get the last execution result for a script"""
        return self._execution_results.get(script_name)
    
    def should_show_notifications_for_script(self, script_name: str) -> bool:
        """Check if notifications should be shown for a script"""
        script_info = self._script_collection.get_script_by_name(script_name)
        if script_info:
            script_key = getattr(script_info, 'identifier', None) or script_info.file_path.stem.lower()
            return self._settings.should_show_script_notifications(script_key)
        return True


class HotkeyModel(QObject):
    """
    Model for managing hotkey assignments and registrations.
    
    Handles hotkey configuration and provides hotkey-to-script mappings.
    """
    
    # Signals for hotkey changes
    hotkey_registered = pyqtSignal(str, str)  # script name, hotkey
    hotkey_unregistered = pyqtSignal(str)  # script name
    hotkey_registration_failed = pyqtSignal(str, str, str)  # script name, hotkey, error
    hotkeys_changed = pyqtSignal()  # General hotkey configuration changed
    
    def __init__(self):
        super().__init__()
        self._settings = SettingsManager()
        self._hotkey_registry = HotkeyRegistry(self._settings)
        
        self._script_hotkeys: Dict[str, str] = {}
        self._load_hotkeys()
        
        logger.info("HotkeyModel initialized")
    
    def get_hotkey_for_script(self, script_name: str) -> Optional[str]:
        """Get the hotkey assigned to a script"""
        return self._script_hotkeys.get(script_name)
    
    def set_hotkey_for_script(self, script_name: str, hotkey: str):
        """Set hotkey for a script"""
        try:
            # Add the hotkey using the registry
            success, error_msg = self._hotkey_registry.add_hotkey(script_name, hotkey)
            
            if success:
                # Update local cache
                old_hotkey = self._script_hotkeys.get(script_name)
                self._script_hotkeys[script_name] = hotkey
                
                self.hotkey_registered.emit(script_name, hotkey)
                self.hotkeys_changed.emit()
                
                logger.info(f"Set hotkey for {script_name}: {hotkey}")
            else:
                self.hotkey_registration_failed.emit(script_name, hotkey, error_msg)
                logger.error(f"Failed to set hotkey for {script_name}: {error_msg}")
            
        except Exception as e:
            logger.error(f"Error setting hotkey for {script_name}: {e}")
            self.hotkey_registration_failed.emit(script_name, hotkey, str(e))
    
    def remove_hotkey_for_script(self, script_name: str):
        """Remove hotkey assignment for a script"""
        if script_name in self._script_hotkeys:
            # Remove using the registry
            if self._hotkey_registry.remove_hotkey(script_name):
                del self._script_hotkeys[script_name]
                
                self.hotkey_unregistered.emit(script_name)
                self.hotkeys_changed.emit()
                
                logger.info(f"Removed hotkey for {script_name}")
    
    def get_all_hotkeys(self) -> Dict[str, str]:
        """Get all script-to-hotkey mappings"""
        return self._script_hotkeys.copy()
    
    def is_hotkey_available(self, hotkey: str, exclude_script: Optional[str] = None) -> bool:
        """Check if a hotkey is available (not assigned to another script)"""
        existing_script = self._hotkey_registry.get_script_for_hotkey(hotkey)
        return existing_script is None or existing_script == exclude_script
    
    def _load_hotkeys(self):
        """Load hotkeys from settings"""
        try:
            # Get all hotkey settings
            all_hotkeys = self._hotkey_registry.get_all_mappings()
            self._script_hotkeys = all_hotkeys
            logger.info(f"Loaded {len(all_hotkeys)} hotkey assignments")
        except Exception as e:
            logger.error(f"Error loading hotkeys: {e}")
            self._script_hotkeys = {}
