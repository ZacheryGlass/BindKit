"""
Service Monitor - Monitors service health and handles auto-restart.

This module provides a QTimer-based health monitoring system that:
- Periodically checks if services are still running
- Detects crashes and failures
- Triggers auto-restart based on configuration
- Implements backoff/delay between restart attempts
"""

import logging
import time
from typing import Dict, Optional, Set
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .service_runtime import ServiceRuntime, ServiceState
from .settings import SettingsManager

logger = logging.getLogger('Core.ServiceMonitor')


class ServiceMonitor(QObject):
    """
    Monitors service health and triggers auto-restart on failure.

    Uses QTimer for periodic checks (every 5 seconds by default).
    Respects service configuration for auto-restart behavior.
    """

    # Signals
    service_crashed = pyqtSignal(str)  # script_name
    service_restarted = pyqtSignal(str)  # script_name
    service_restart_failed = pyqtSignal(str, str)  # script_name, error
    service_restart_limit_reached = pyqtSignal(str)  # script_name
    service_state_changed = pyqtSignal(str, str)  # script_name, state

    def __init__(self, service_runtime: ServiceRuntime, settings: SettingsManager,
                 check_interval_ms: int = 5000):
        """
        Initialize service monitor.

        Args:
            service_runtime: ServiceRuntime instance to monitor
            settings: SettingsManager instance for configuration
            check_interval_ms: Check interval in milliseconds (default 5000 = 5 seconds)
        """
        super().__init__()

        self.service_runtime = service_runtime
        self.settings = settings
        self.check_interval_ms = check_interval_ms

        # Track services that are pending restart (to prevent duplicate restart attempts)
        self._pending_restarts: Set[str] = set()

        # Track last known states to detect state changes
        self._last_states: Dict[str, ServiceState] = {}

        # Set up timer for periodic health checks
        self._timer = QTimer()
        self._timer.timeout.connect(self._check_services)
        self._timer.setInterval(check_interval_ms)

        self._running = False

        logger.info(f"ServiceMonitor initialized (check interval: {check_interval_ms}ms)")

    def start(self):
        """Start monitoring services."""
        if not self._running:
            self._running = True
            self._timer.start()
            logger.info("ServiceMonitor started")

    def stop(self):
        """Stop monitoring services."""
        if self._running:
            self._running = False
            self._timer.stop()
            logger.info("ServiceMonitor stopped")

    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running

    def _check_services(self):
        """Periodic health check of all services."""
        try:
            all_services = self.service_runtime.get_all_services()

            # Check each active service
            for script_name, handle in all_services.items():
                current_state = self.service_runtime.get_status(script_name)
                last_state = self._last_states.get(script_name)

                # Detect state changes
                if last_state != current_state:
                    logger.debug(f"Service '{script_name}' state changed: {last_state} -> {current_state}")
                    self.service_state_changed.emit(script_name, current_state.value)
                    self._last_states[script_name] = current_state

                # Detect crash (process terminated unexpectedly)
                if current_state == ServiceState.CRASHED:
                    self._handle_crashed_service(script_name, handle)

        except Exception as e:
            logger.error(f"Error during service health check: {e}")

    def _handle_crashed_service(self, script_name: str, handle):
        """Handle a crashed service."""
        # Emit crash signal
        self.service_crashed.emit(script_name)
        logger.warning(f"Service '{script_name}' crashed (PID {handle.pid})")

        # Check if already pending restart
        if script_name in self._pending_restarts:
            logger.debug(f"Service '{script_name}' already pending restart, skipping")
            return

        # Get service configuration
        config = self.settings.get_service_config(script_name)

        # Check if auto-restart is enabled
        if not config.get('auto_restart', True):
            logger.info(f"Auto-restart disabled for service '{script_name}'")
            return

        # Check restart count against max restarts
        if handle.restart_count >= config.get('max_restarts', 3):
            logger.error(f"Service '{script_name}' reached max restart limit ({handle.restart_count})")
            self.service_restart_limit_reached.emit(script_name)
            return

        # Schedule restart with delay
        restart_delay_ms = config.get('restart_delay_seconds', 5) * 1000
        self._pending_restarts.add(script_name)

        logger.info(f"Scheduling restart for service '{script_name}' in {restart_delay_ms}ms")

        # Use QTimer.singleShot for delayed restart
        QTimer.singleShot(restart_delay_ms, lambda: self._restart_service(script_name))

    def _restart_service(self, script_name: str):
        """Restart a crashed service."""
        try:
            # Remove from pending restarts
            self._pending_restarts.discard(script_name)

            logger.info(f"Attempting to restart service '{script_name}'")

            # Get the service handle (if it still exists)
            handle = self.service_runtime.get_handle(script_name)
            if not handle:
                logger.warning(f"Service '{script_name}' handle not found, cannot restart")
                return

            # Increment restart count
            handle.restart_count += 1

            # Start the service with original arguments
            new_handle = self.service_runtime.start_service(
                script_name,
                handle.script_path,
                handle.arguments  # Use original arguments
            )

            # Preserve restart count
            new_handle.restart_count = handle.restart_count

            logger.info(f"Service '{script_name}' restarted successfully (restart #{handle.restart_count})")
            self.service_restarted.emit(script_name)

        except Exception as e:
            error_msg = f"Failed to restart service '{script_name}': {e}"
            logger.error(error_msg)
            self.service_restart_failed.emit(script_name, str(e))

    def reset_restart_count(self, script_name: str):
        """Reset the restart count for a service (e.g., after manual intervention)."""
        handle = self.service_runtime.get_handle(script_name)
        if handle:
            handle.restart_count = 0
            logger.info(f"Reset restart count for service '{script_name}'")

    def get_service_info(self, script_name: str) -> Optional[Dict[str, any]]:
        """Get detailed information about a service."""
        handle = self.service_runtime.get_handle(script_name)
        if not handle:
            return None

        state = self.service_runtime.get_status(script_name)
        config = self.settings.get_service_config(script_name)

        return {
            'script_name': script_name,
            'state': state.value,
            'pid': handle.pid,
            'start_time': handle.start_time,
            'uptime_seconds': time.time() - handle.start_time if state == ServiceState.RUNNING else 0,
            'restart_count': handle.restart_count,
            'log_path': str(handle.log_file_path),
            'config': config
        }

    def get_all_service_info(self) -> Dict[str, Dict[str, any]]:
        """Get information for all services."""
        result = {}
        for script_name in self.service_runtime.get_all_services():
            info = self.get_service_info(script_name)
            if info:
                result[script_name] = info
        return result
