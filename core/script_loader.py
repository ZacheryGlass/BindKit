import os
import sys
import importlib.util
import traceback
import logging
import concurrent.futures
from pathlib import Path
from typing import List, Optional, Dict, Any
from .script_analyzer import ScriptAnalyzer, ScriptInfo
from .script_executor import ScriptExecutor
from .exceptions import ScriptLoadError
from .settings import SettingsManager

logger = logging.getLogger('Core.ScriptLoader')

class ScriptLoader:
    
    def __init__(self, scripts_directory: str = "scripts"):
        self.scripts_directory = Path(scripts_directory)
        self.loaded_scripts: Dict[str, ScriptInfo] = {}
        self.failed_scripts: Dict[str, str] = {}
        self.settings = SettingsManager()
        self.analyzer = ScriptAnalyzer()
        self.executor = ScriptExecutor(self.settings)
        logger.info(f"ScriptLoader initialized with directory: {self.scripts_directory.absolute()}")
    
    def discover_scripts(self) -> List[ScriptInfo]:
        logger.info(f"Discovering scripts in: {self.scripts_directory}")
        scripts = []
        self.failed_scripts.clear()
        
        # Use ThreadPoolExecutor for parallel script discovery
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # Submit both discovery tasks to run in parallel
            default_future = executor.submit(self._discover_default_scripts)
            external_future = executor.submit(self._discover_external_scripts)
            
            # Wait for both to complete and collect results
            try:
                default_scripts = default_future.result(timeout=10)
                scripts.extend(default_scripts)
            except Exception as e:
                logger.error(f"Error discovering default scripts: {e}")
            
            try:
                external_scripts = external_future.result(timeout=10)
                scripts.extend(external_scripts)
            except Exception as e:
                logger.error(f"Error discovering external scripts: {e}")
        
        # Ensure deterministic ordering regardless of async completion order
        scripts.sort(key=lambda info: info.display_name.lower())

        logger.info(f"Script discovery complete: {len(scripts)} total scripts loaded, {len(self.failed_scripts)} failed")
        return scripts
    
    def _discover_default_scripts(self) -> List[ScriptInfo]:
        """Discover scripts from the default scripts directory."""
        logger.debug(f"Discovering default scripts in: {self.scripts_directory}")
        scripts = []
        
        if not self.scripts_directory.exists():
            logger.warning(f"Scripts directory does not exist, creating: {self.scripts_directory}")
            self.scripts_directory.mkdir(parents=True, exist_ok=True)
            return scripts
        
        # Discover all supported script types
        script_files = []
        for pattern in ["*.py", "*.ps1", "*.bat", "*.cmd", "*.sh"]:
            script_files.extend(self.scripts_directory.glob(pattern))

        logger.info(f"Found {len(script_files)} script files in scripts directory")

        # Filter out files starting with "__"
        script_files = [f for f in script_files if not f.name.startswith("__")]
        
        # Sort files to ensure consistent ordering
        script_files.sort(key=lambda f: f.name.lower())
        
        # Analyze scripts in parallel using thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all script analysis tasks
            future_to_file = {
                executor.submit(self._analyze_single_script, script_file): script_file
                for script_file in script_files
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_file):
                script_file = future_to_file[future]
                try:
                    script_info = future.result(timeout=5)
                    if script_info and script_info.is_executable:
                        scripts.append(script_info)
                        self.loaded_scripts[script_file.stem] = script_info
                        logger.info(f"Successfully analyzed default script: {script_file.name}")
                    elif script_info:
                        error_msg = f"Script not executable: {script_info.error}"
                        self.failed_scripts[script_file.name] = error_msg
                        logger.warning(f"Default script {script_file.name} is not executable: {script_info.error}")
                except Exception as e:
                    error_msg = f"Failed to analyze {script_file.name}: {str(e)}"
                    self.failed_scripts[script_file.name] = error_msg
                    logger.error(f"Error analyzing default script: {error_msg}")
        
        logger.info(f"Default script discovery: {len(scripts)} loaded")
        return scripts
    
    def _analyze_single_script(self, script_file: Path) -> Optional[ScriptInfo]:
        """Analyze a single script file. Thread-safe method for parallel execution."""
        logger.debug(f"Attempting to analyze: {script_file.name}")
        try:
            # Create a new analyzer instance for thread safety
            # Pass settings so analyzer can check service configuration
            analyzer = ScriptAnalyzer(self.settings)
            return analyzer.analyze_script(script_file)
        except Exception as e:
            logger.error(f"Error in _analyze_single_script for {script_file.name}: {e}")
            raise
    
    def _discover_external_scripts(self) -> List[ScriptInfo]:
        """Discover scripts from external paths configured in settings."""
        logger.debug("Discovering external scripts")
        scripts = []
        
        external_scripts = self.settings.get_external_scripts()
        logger.info(f"Found {len(external_scripts)} configured external scripts")
        
        if not external_scripts:
            return scripts
        
        # Analyze external scripts in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all external script analysis tasks
            future_to_script = {}
            for script_name, script_path in external_scripts.items():
                # Validate the path still exists and is valid
                if not self.settings.validate_external_script_path(script_path):
                    error_msg = f"External script path is invalid or missing: {script_path}"
                    self.failed_scripts[f"{script_name} (external)"] = error_msg
                    logger.warning(error_msg)
                    continue
                
                future = executor.submit(self._analyze_external_script, script_name, script_path)
                future_to_script[future] = (script_name, script_path)
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_script):
                script_name, script_path = future_to_script[future]
                try:
                    script_info = future.result(timeout=5)
                    if script_info and script_info.is_executable:
                        # Override the display name with the configured name
                        script_info.display_name = script_name
                        scripts.append(script_info)
                        self.loaded_scripts[script_name] = script_info
                        logger.info(f"Successfully analyzed external script: {script_name} -> {script_path}")
                    elif script_info:
                        error_msg = f"External script not executable: {script_info.error}"
                        self.failed_scripts[f"{script_name} (external)"] = error_msg
                        logger.warning(f"External script {script_name} is not executable: {script_info.error}")
                except Exception as e:
                    error_msg = f"Failed to analyze external script {script_name} at {script_path}: {str(e)}"
                    self.failed_scripts[f"{script_name} (external)"] = error_msg
                    logger.error(error_msg)
        
        logger.info(f"External script discovery: {len(scripts)} loaded")
        return scripts
    
    def _analyze_external_script(self, script_name: str, script_path: str) -> Optional[ScriptInfo]:
        """Analyze a single external script. Thread-safe method for parallel execution."""
        logger.debug(f"Attempting to analyze external script: {script_name} -> {script_path}")
        try:
            script_file = Path(script_path)
            # Create a new analyzer instance for thread safety
            # Pass settings so analyzer can check service configuration
            analyzer = ScriptAnalyzer(self.settings)
            return analyzer.analyze_script(script_file)
        except Exception as e:
            logger.error(f"Error in _analyze_external_script for {script_name}: {e}")
            raise
    
    def execute_script(self, script_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a script by name with provided arguments."""
        if script_name not in self.loaded_scripts:
            return {
                'success': False,
                'message': f'Script "{script_name}" not found'
            }
        
        script_info = self.loaded_scripts[script_name]
        
        # Get arguments from settings if not provided
        if arguments is None:
            arguments = self.get_script_arguments(script_name)
        
        # Validate arguments
        validation_errors = self.executor.validate_arguments(script_info, arguments)
        if validation_errors:
            return {
                'success': False,
                'message': f'Argument validation failed: {"; ".join(validation_errors)}'
            }
        
        # Execute the script
        result = self.executor.execute_script(script_info, arguments)
        
        return {
            'success': result.success,
            'message': result.message,
            'output': result.output,
            'error': result.error,
            'data': result.data
        }
    
    def reload_scripts(self) -> List[ScriptInfo]:
        logger.info("Reloading all scripts")
        self.loaded_scripts.clear()
        
        # Clear executor's module cache thoroughly (removes from sys.modules too)
        try:
            removed = self.executor.clear_module_cache()
            logger.debug(f"Executor module cache cleared: {removed} module(s) removed")
        except Exception:
            # Backward compatibility: fall back to simple clear
            try:
                self.executor.loaded_modules.clear()
            except Exception:
                pass
        
        return self.discover_scripts()
    
    def get_script(self, name: str) -> Optional[ScriptInfo]:
        return self.loaded_scripts.get(name)
    
    def get_failed_scripts(self) -> Dict[str, str]:
        return self.failed_scripts.copy()
    
    def get_script_display_name(self, script_info: ScriptInfo) -> str:
        """Get the effective display name for a script (custom name if set, otherwise original)."""
        try:
            original_name = script_info.display_name
            return self.settings.get_effective_name(original_name)
        except Exception as e:
            logger.error(f"Error getting display name for script: {e}")
            return "Unknown Script"
    
    def get_script_arguments(self, script_name: str) -> Dict[str, Any]:
        """Get configured arguments for a script from settings."""
        return self.settings.get_script_arguments(script_name)
    
    def set_script_arguments(self, script_name: str, arguments: Dict[str, Any]):
        """Save arguments configuration for a script to settings."""
        self.settings.set_script_arguments(script_name, arguments)
    
    def get_script_status(self, script_name: str) -> str:
        """Get current status of a script."""
        if script_name not in self.loaded_scripts:
            return "Not Found"
        
        script_info = self.loaded_scripts[script_name]
        return self.executor.get_script_status(script_info)
    
    def get_all_scripts(self) -> List[ScriptInfo]:
        """Get all loaded script info objects."""
        return list(self.loaded_scripts.values())
    
    def is_external_script(self, script_name: str) -> bool:
        """Check if a script is an external script (loaded from external path)."""
        external_scripts = self.settings.get_external_scripts()
        return script_name in external_scripts
    
    def get_external_script_path(self, script_name: str) -> Optional[str]:
        """Get the external path for an external script."""
        return self.settings.get_external_script_path(script_name)
    
    def refresh_external_scripts(self) -> List[ScriptInfo]:
        """Refresh only external scripts without affecting default scripts."""
        logger.info("Refreshing external scripts")
        
        # First, identify all currently loaded external scripts
        # These are scripts that are NOT in the default scripts directory
        default_script_names = set()
        if self.scripts_directory.exists():
            for script_file in self.scripts_directory.glob("*.py"):
                if not script_file.name.startswith("__"):
                    default_script_names.add(script_file.stem)
        
        # Remove ALL external scripts from loaded_scripts (not just the ones still in settings)
        scripts_to_remove = []
        for script_name, script_info in self.loaded_scripts.items():
            # If it's not a default script, it must be external
            if script_name not in default_script_names:
                scripts_to_remove.append(script_name)
        
        for script_name in scripts_to_remove:
            logger.debug(f"Removing external script from loaded: {script_name}")
            del self.loaded_scripts[script_name]
        
        # Remove external script failures from failed_scripts
        failed_keys_to_remove = [key for key in self.failed_scripts.keys() if "(external)" in key]
        for key in failed_keys_to_remove:
            del self.failed_scripts[key]
        
        # Rediscover external scripts
        external_scripts = self._discover_external_scripts()
        
        # Return all currently loaded scripts (default + refreshed external)
        return self.get_all_scripts()
