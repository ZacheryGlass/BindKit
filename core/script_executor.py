import subprocess
import sys
import importlib.util
import json
import logging
import time
import weakref
import gc
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from collections import OrderedDict

from .script_analyzer import ScriptInfo, ExecutionStrategy, ArgumentInfo
from .service_runtime import ServiceRuntime, ServiceHandle, ServiceState
from .schedule_runtime import ScheduleRuntime, ScheduleHandle

logger = logging.getLogger('Core.ScriptExecutor')

@dataclass
class ExecutionResult:
    success: bool
    message: str = ""
    output: str = ""
    error: str = ""
    return_code: Optional[int] = None
    data: Optional[Dict[str, Any]] = None

class ScriptExecutor:
    def __init__(self, settings=None, max_cache_size=20, cache_ttl_seconds=1800):
        # Use OrderedDict for LRU cache behavior
        self.loaded_modules = OrderedDict()
        self.module_access_times = {}  # Track last access time
        self.settings = settings
        self.max_cache_size = max_cache_size  # Maximum number of cached modules (reduced from 50 to 20)
        self.cache_ttl_seconds = cache_ttl_seconds  # Time-to-live in seconds (reduced from 1 hour to 30 minutes)
        # Track when cache cleanup last ran (0 enables immediate cleanup on first call)
        self._last_cleanup_time = 0

        # Initialize service runtime for long-running scripts
        self.service_runtime = ServiceRuntime()

        # Initialize schedule runtime for periodic script execution
        self.schedule_runtime = ScheduleRuntime()

        logger.info("ScriptExecutor initialized with ServiceRuntime and ScheduleRuntime support")
    
    def execute_script(self, script_info: ScriptInfo, arguments: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """Execute a script using the appropriate strategy."""
        # Perform periodic cleanup
        self._cleanup_stale_modules()
        
        if not script_info.is_executable:
            return ExecutionResult(
                success=False,
                error=f"Script is not executable: {script_info.error}"
            )
        
        if arguments is None:
            arguments = {}
        
        logger.debug(f"Executing script {script_info.display_name} with strategy {script_info.execution_strategy}")
        
        try:
            if script_info.execution_strategy == ExecutionStrategy.SUBPROCESS:
                return self._execute_subprocess(script_info, arguments)
            elif script_info.execution_strategy == ExecutionStrategy.FUNCTION_CALL:
                return self._execute_function_call(script_info, arguments)
            elif script_info.execution_strategy == ExecutionStrategy.MODULE_EXEC:
                return self._execute_module(script_info, arguments)
            elif script_info.execution_strategy == ExecutionStrategy.SERVICE:
                return self._execute_service(script_info, arguments)
            else:
                return ExecutionResult(
                    success=False,
                    error=f"Unknown execution strategy: {script_info.execution_strategy}"
                )
                
        except Exception as e:
            logger.error(f"Error executing script {script_info.display_name}: {str(e)}")
            return ExecutionResult(
                success=False,
                error=f"Execution error: {str(e)}"
            )
    
    def _execute_subprocess(self, script_info: ScriptInfo, arguments: Dict[str, Any]) -> ExecutionResult:
        """Execute script as subprocess with command line arguments."""
        cmd = [sys.executable, str(script_info.file_path)]
        
        # Add arguments
        for arg_info in script_info.arguments:
            if arg_info.name in arguments:
                value = arguments[arg_info.name]
                if value is not None and value != "":
                    cmd.extend([f"--{arg_info.name}", str(value)])
            elif arg_info.required:
                return ExecutionResult(
                    success=False,
                    error=f"Required argument '{arg_info.name}' not provided"
                )
        
        logger.debug(f"Executing command: {' '.join(cmd)}")

        # Force UTF-8 I/O so scripts with non-ASCII output don't crash on Windows consoles
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env.setdefault('PYTHONUTF8', '1')

        process = None
        try:
            used_timeout = self.settings.get_script_timeout_seconds() if self.settings else 30
            
            # Use Popen for better control over process lifecycle
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # Wait for completion with timeout
            try:
                stdout, stderr = process.communicate(timeout=used_timeout)
                returncode = process.returncode
            except subprocess.TimeoutExpired:
                logger.warning(f"Script execution timed out, terminating process: {script_info.display_name}")
                
                # Attempt graceful termination first
                try:
                    process.terminate()
                    stdout, stderr = process.communicate(timeout=5)  # Give 5 seconds for graceful exit
                    returncode = process.returncode
                except subprocess.TimeoutExpired:
                    # Force kill if graceful termination failed
                    logger.warning(f"Force killing unresponsive script process: {script_info.display_name}")
                    process.kill()
                    stdout, stderr = process.communicate()  # Clean up pipes
                    returncode = process.returncode
                
                return ExecutionResult(
                    success=False,
                    message=f"Script execution timed out ({used_timeout} seconds)",
                    output=stdout.strip() if stdout else "",
                    error=stderr.strip() if stderr else "",
                    return_code=returncode
                )
            
            success = returncode == 0
            output = stdout.strip() if stdout else ""
            error = stderr.strip() if stderr else ""
            
            # Try to parse output as JSON for structured data
            data = None
            message = output
            if output:
                try:
                    data = json.loads(output)
                    if isinstance(data, dict):
                        message = data.get('message', output)
                        success = data.get('success', success)
                except json.JSONDecodeError:
                    pass
            
            return ExecutionResult(
                success=success,
                message=message,
                output=output,
                error=error,
                return_code=returncode,
                data=data
            )
            
        except Exception as e:
            # Ensure process is cleaned up on any exception
            if process:
                try:
                    if process.poll() is None:  # Process is still running
                        logger.warning(f"Cleaning up subprocess after exception: {script_info.display_name}")
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up subprocess: {cleanup_error}")
            
            return ExecutionResult(
                success=False,
                error=f"Subprocess execution failed: {str(e)}"
            )
        finally:
            # Final cleanup to ensure no process handles are left open
            if process:
                try:
                    # Ensure pipes are closed
                    if process.stdout:
                        process.stdout.close()
                    if process.stderr:
                        process.stderr.close()
                    if process.stdin:
                        process.stdin.close()
                except Exception:
                    pass
    
    def _execute_function_call(self, script_info: ScriptInfo, arguments: Dict[str, Any]) -> ExecutionResult:
        """Execute script by importing and calling main function."""
        try:
            # Load or reload the module
            module_name = script_info.file_path.stem
            
            if module_name in self.loaded_modules:
                # Move to end for LRU ordering
                self.loaded_modules.move_to_end(module_name)
                self.module_access_times[module_name] = time.time()
                
                # Reload module for changes; ensure present in sys.modules for reload()
                module = self.loaded_modules[module_name]
                try:
                    if module_name not in sys.modules:
                        sys.modules[module_name] = module
                    importlib.reload(module)
                except Exception:
                    # If reload fails (e.g., not in sys.modules), fall back to fresh load
                    spec = importlib.util.spec_from_file_location(module_name, script_info.file_path)
                    if spec is None or spec.loader is None:
                        return ExecutionResult(
                            success=False,
                            error=f"Could not load module spec for {script_info.file_path}"
                        )
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    self._cache_module(module_name, module)
            else:
                # Load module for first time
                spec = importlib.util.spec_from_file_location(module_name, script_info.file_path)
                if spec is None or spec.loader is None:
                    return ExecutionResult(
                        success=False,
                        error=f"Could not load module spec for {script_info.file_path}"
                    )
                
                module = importlib.util.module_from_spec(spec)
                # Insert into sys.modules before execution to support reloads/circular imports
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                self._cache_module(module_name, module)
            
            # Get the main function
            if not hasattr(module, script_info.main_function or 'main'):
                return ExecutionResult(
                    success=False,
                    error=f"Function '{script_info.main_function or 'main'}' not found in script"
                )
            
            main_func = getattr(module, script_info.main_function or 'main')
            
            # Prepare function arguments
            func_args = []
            func_kwargs = {}
            
            # Check function signature to determine how to pass arguments
            import inspect
            sig = inspect.signature(main_func)
            
            for param_name, param in sig.parameters.items():
                if param_name in arguments:
                    if param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
                        func_kwargs[param_name] = arguments[param_name]
                    elif param.kind == inspect.Parameter.POSITIONAL_ONLY:
                        func_args.append(arguments[param_name])
            
            # Call the function
            result = main_func(*func_args, **func_kwargs)
            
            # Process the result
            success = True
            message = ""
            data = None
            
            if result is None:
                message = "Script executed successfully"
            elif isinstance(result, dict):
                data = result
                success = result.get('success', True)
                message = result.get('message', 'Script executed successfully')
            elif isinstance(result, str):
                message = result
            elif isinstance(result, bool):
                success = result
                message = "Script executed successfully" if result else "Script execution failed"
            else:
                message = str(result)
            
            return ExecutionResult(
                success=success,
                message=message,
                data=data
            )
            
        except Exception as e:
            logger.error(f"Function call execution failed: {str(e)}")
            return ExecutionResult(
                success=False,
                error=f"Function execution failed: {str(e)}"
            )
    
    def _execute_module(self, script_info: ScriptInfo, arguments: Dict[str, Any]) -> ExecutionResult:
        """Execute script by importing the entire module."""
        try:
            module_name = script_info.file_path.stem
            
            # Set up arguments in sys.argv if the script expects them
            original_argv = sys.argv.copy()
            
            try:
                # Build argv list
                sys.argv = [str(script_info.file_path)]
                for arg_info in script_info.arguments:
                    if arg_info.name in arguments:
                        value = arguments[arg_info.name]
                        if value is not None and value != "":
                            sys.argv.extend([f"--{arg_info.name}", str(value)])
                
                # Import and execute the module
                spec = importlib.util.spec_from_file_location(module_name, script_info.file_path)
                if spec is None or spec.loader is None:
                    return ExecutionResult(
                        success=False,
                        error=f"Could not load module spec for {script_info.file_path}"
                    )
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                return ExecutionResult(
                    success=True,
                    message="Script executed successfully"
                )
                
            finally:
                # Restore original argv
                sys.argv = original_argv
                
        except Exception as e:
            logger.error(f"Module execution failed: {str(e)}")
            return ExecutionResult(
                success=False,
                error=f"Module execution failed: {str(e)}"
            )
    
    def _execute_service(self, script_info: ScriptInfo, arguments: Dict[str, Any]) -> ExecutionResult:
        """Execute script as a long-running background service."""
        try:
            script_name = script_info.file_path.stem

            # Check if service is already running
            if self.service_runtime.is_running(script_name):
                return ExecutionResult(
                    success=False,
                    error=f"Service '{script_name}' is already running"
                )

            # Start the service
            handle = self.service_runtime.start_service(
                script_name,
                script_info.file_path,
                arguments
            )

            return ExecutionResult(
                success=True,
                message=f"Service started with PID {handle.pid}",
                data={
                    'pid': handle.pid,
                    'start_time': handle.start_time,
                    'log_path': str(handle.log_file_path)
                }
            )

        except Exception as e:
            logger.error(f"Service execution failed: {str(e)}")
            return ExecutionResult(
                success=False,
                error=f"Service execution failed: {str(e)}"
            )

    def stop_service(self, script_name: str, timeout: int = 10) -> ExecutionResult:
        """Stop a running service.

        Args:
            script_name: Name of the service script (file stem)
            timeout: Seconds to wait for graceful shutdown

        Returns:
            ExecutionResult indicating success or failure
        """
        try:
            if not self.service_runtime.is_running(script_name):
                return ExecutionResult(
                    success=False,
                    error=f"Service '{script_name}' is not running"
                )

            success = self.service_runtime.stop_service(script_name, timeout)

            if success:
                return ExecutionResult(
                    success=True,
                    message=f"Service '{script_name}' stopped"
                )
            else:
                return ExecutionResult(
                    success=False,
                    error=f"Failed to stop service '{script_name}'"
                )

        except Exception as e:
            logger.error(f"Error stopping service '{script_name}': {e}")
            return ExecutionResult(
                success=False,
                error=f"Error stopping service: {str(e)}"
            )

    def restart_service(self, script_info: ScriptInfo, arguments: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """Restart a running service.

        Args:
            script_info: ScriptInfo for the service
            arguments: Optional arguments for the service

        Returns:
            ExecutionResult indicating success or failure
        """
        script_name = script_info.file_path.stem

        # Stop the service if running
        if self.service_runtime.is_running(script_name):
            stop_result = self.stop_service(script_name)
            if not stop_result.success:
                return stop_result

        # Start the service
        return self._execute_service(script_info, arguments or {})

    def get_service_status(self, script_name: str) -> ServiceState:
        """Get the status of a service.

        Args:
            script_name: Name of the service script (file stem)

        Returns:
            ServiceState enum value
        """
        return self.service_runtime.get_status(script_name)

    def get_all_services(self) -> Dict[str, ServiceHandle]:
        """Get all active service handles."""
        return self.service_runtime.get_all_services()

    def is_service_running(self, script_name: str) -> bool:
        """Check if a service is running.

        Args:
            script_name: Name of the service script (file stem)

        Returns:
            True if service is running, False otherwise
        """
        return self.service_runtime.is_running(script_name)

    def start_scheduled_execution(self, script_info: ScriptInfo, interval_seconds: int, arguments: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """Start scheduled periodic execution of a script.

        Args:
            script_info: ScriptInfo for the script
            interval_seconds: Interval between executions in seconds
            arguments: Optional script arguments

        Returns:
            ExecutionResult indicating success or failure
        """
        try:
            script_name = script_info.file_path.stem

            # Check if schedule already exists
            if self.schedule_runtime.is_scheduled(script_name):
                return ExecutionResult(
                    success=False,
                    error=f"Schedule for '{script_name}' is already active"
                )

            # Create execution callback that will be called by the schedule
            # Capture immutable copies to prevent stale data from schedule updates
            def execution_callback(name: str, _script_info=script_info, _args=dict(arguments or {})):
                """Called when schedule timer fires."""
                result = self.execute_script(_script_info, _args)
                if result.success:
                    logger.info(f"Scheduled execution of '{name}' completed successfully")
                else:
                    logger.warning(f"Scheduled execution of '{name}' failed: {result.error}")

            # Start the schedule
            handle = self.schedule_runtime.start_schedule(
                script_name,
                script_info.file_path,
                interval_seconds,
                execution_callback,
                self.settings
            )

            return ExecutionResult(
                success=True,
                message=f"Schedule started for '{script_name}' (interval: {interval_seconds}s)",
                data={
                    'script_name': script_name,
                    'interval_seconds': interval_seconds,
                    'next_run': handle.next_run
                }
            )

        except Exception as e:
            logger.error(f"Failed to start schedule: {e}")
            return ExecutionResult(
                success=False,
                error=f"Failed to start schedule: {str(e)}"
            )

    def stop_scheduled_execution(self, script_name: str) -> ExecutionResult:
        """Stop scheduled execution of a script.

        Args:
            script_name: Name of the script (file stem)

        Returns:
            ExecutionResult indicating success or failure
        """
        try:
            if not self.schedule_runtime.is_scheduled(script_name):
                logger.info(f"Schedule for '{script_name}' already stopped")
                return ExecutionResult(
                    success=True,
                    message=f"Schedule for '{script_name}' already stopped",
                    data={'already_stopped': True}
                )

            success = self.schedule_runtime.stop_schedule(script_name)

            if success:
                return ExecutionResult(
                    success=True,
                    message=f"Schedule for '{script_name}' stopped"
                )
            else:
                return ExecutionResult(
                    success=False,
                    error=f"Failed to stop schedule for '{script_name}'"
                )

        except Exception as e:
            logger.error(f"Error stopping schedule: {e}")
            return ExecutionResult(
                success=False,
                error=f"Error stopping schedule: {str(e)}"
            )

    def is_schedule_running(self, script_name: str) -> bool:
        """Check if a script has an active schedule.

        Args:
            script_name: Name of the script (file stem)

        Returns:
            True if schedule is running, False otherwise
        """
        return self.schedule_runtime.is_scheduled(script_name)

    def get_schedule_status(self, script_name: str) -> str:
        """Get the status of a script's schedule.

        Args:
            script_name: Name of the script (file stem)

        Returns:
            Human-readable status string
        """
        return self.schedule_runtime.get_schedule_status(script_name)

    def get_all_schedules(self):
        """Get all active schedules."""
        return self.schedule_runtime.get_all_schedules()

    def get_script_status(self, script_info: ScriptInfo) -> str:
        """Get current status of a script (if applicable)."""
        # For now, return a simple status
        if not script_info.is_executable:
            return "Error"

        # Check if script is a service and return service status
        if script_info.execution_strategy == ExecutionStrategy.SERVICE:
            script_name = script_info.file_path.stem
            state = self.get_service_status(script_name)
            return state.value.capitalize()

        # Could be enhanced to check actual status for toggle/cycle scripts
        return "Ready"
    
    def validate_arguments(self, script_info: ScriptInfo, arguments: Dict[str, Any]) -> List[str]:
        """Validate provided arguments against script requirements."""
        errors = []
        
        for arg_info in script_info.arguments:
            if arg_info.required and arg_info.name not in arguments:
                errors.append(f"Required argument '{arg_info.name}' is missing")
            
            if arg_info.name in arguments:
                value = arguments[arg_info.name]
                
                # Check choices
                if arg_info.choices and value not in arg_info.choices:
                    errors.append(f"Argument '{arg_info.name}' must be one of: {', '.join(arg_info.choices)}")
                
                # Basic type checking
                if arg_info.type == 'int':
                    try:
                        int(value)
                    except (ValueError, TypeError):
                        errors.append(f"Argument '{arg_info.name}' must be an integer")
                elif arg_info.type == 'float':
                    try:
                        float(value)
                    except (ValueError, TypeError):
                        errors.append(f"Argument '{arg_info.name}' must be a number")
        
        return errors
    
    def _cache_module(self, module_name: str, module):
        """Cache a module with LRU eviction if needed."""
        # Check if we need to evict old modules
        if len(self.loaded_modules) >= self.max_cache_size:
            # Remove least recently used (first item)
            oldest_name, oldest_module = self.loaded_modules.popitem(last=False)
            self.module_access_times.pop(oldest_name, None)
            
            # Aggressive cleanup for evicted module
            self._cleanup_module(oldest_name, oldest_module)
            logger.debug(f"Evicted module from cache: {oldest_name}")
        
        # Add new module
        self.loaded_modules[module_name] = module
        self.module_access_times[module_name] = time.time()
    
    def _cleanup_stale_modules(self):
        """Remove modules that haven't been accessed recently."""
        current_time = time.time()

        # Run cleanup no more often than the smaller of 5 minutes or the configured TTL
        min_interval = min(300, max(1, self.cache_ttl_seconds))
        if current_time - self._last_cleanup_time < min_interval:
            return
        
        self._last_cleanup_time = current_time
        stale_modules = []
        
        # Find stale modules
        for module_name, last_access in self.module_access_times.items():
            if current_time - last_access > self.cache_ttl_seconds:
                stale_modules.append(module_name)
        
        # Remove stale modules with proper cleanup
        for module_name in stale_modules:
            if module_name in self.loaded_modules:
                module = self.loaded_modules[module_name]
                del self.loaded_modules[module_name]
                del self.module_access_times[module_name]
                
                # Aggressive cleanup for stale module
                self._cleanup_module(module_name, module)
                logger.debug(f"Removed stale module from cache: {module_name}")
        
        if stale_modules:
            # Force garbage collection after cleanup
            collected = gc.collect()
            logger.info(f"Cleaned up {len(stale_modules)} stale module(s) from cache, collected {collected} objects")
    
    def clear_module_cache(self):
        """Manually clear all cached modules."""
        count = len(self.loaded_modules)
        
        # Remove all modules with proper cleanup
        for module_name in list(self.loaded_modules.keys()):
            module = self.loaded_modules.get(module_name)
            if module:
                self._cleanup_module(module_name, module)
        
        self.loaded_modules.clear()
        self.module_access_times.clear()
        
        # Force garbage collection after clearing cache
        collected = gc.collect()
        logger.info(f"Cleared {count} module(s) from cache, collected {collected} objects")
        return count
    
    def _cleanup_module(self, module_name: str, module):
        """Aggressively clean up a module to prevent memory retention.
        
        Args:
            module_name: Name of the module being cleaned up
            module: The module object to clean up
        """
        try:
            # Remove from sys.modules first
            sys.modules.pop(module_name, None)
            
            # Clear module's __dict__ to break circular references
            if hasattr(module, '__dict__'):
                module_dict = module.__dict__.copy()
                module.__dict__.clear()
                
                # Explicitly delete references to help garbage collection
                for key, value in module_dict.items():
                    try:
                        # Clear any callable objects that might hold references
                        if hasattr(value, '__dict__'):
                            value.__dict__.clear()
                    except Exception:
                        pass  # Some objects might not allow modification
                del module_dict
            
            # Clear any cached attributes
            if hasattr(module, '__cached__'):
                module.__cached__ = None
            if hasattr(module, '__spec__'):
                module.__spec__ = None
            if hasattr(module, '__loader__'):
                module.__loader__ = None
                
            logger.debug(f"Aggressively cleaned up module: {module_name}")
            
        except Exception as e:
            logger.warning(f"Error during aggressive module cleanup for {module_name}: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the module cache."""
        current_time = time.time()
        stats = {
            'cached_modules': len(self.loaded_modules),
            'max_cache_size': self.max_cache_size,
            'cache_ttl_seconds': self.cache_ttl_seconds,
            'modules': []
        }
        
        for module_name in self.loaded_modules:
            last_access = self.module_access_times.get(module_name, 0)
            stats['modules'].append({
                'name': module_name,
                'age_seconds': int(current_time - last_access) if last_access else None
            })
        
        return stats
