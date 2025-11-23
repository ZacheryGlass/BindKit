"""
Main entry point for BindKit using MVC architecture.

This file sets up the MVC components and coordinates the application startup
while maintaining clear separation of concerns.
"""
import sys
import os
import logging
import argparse
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMessageBox
from PyQt6.QtCore import Qt, QLockFile, QDir, QStandardPaths, QMutex, QTimer
import signal
import atexit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import MVC components
from controllers.app_controller import AppController
from controllers.script_controller import ScriptController
from controllers.tray_controller import TrayController
from controllers.settings_controller import SettingsController
from views.tray_view import TrayView
from views.main_view import MainView
from views.settings_view import SettingsView
from views.hotkey_config_view import HotkeyConfigView
from views.preset_editor_view import PresetEditorView
from core.hotkey_manager import HotkeyManager
from core.memory_monitor import get_memory_monitor
from core.theme_manager import ThemeManager
from core.settings import SettingsManager


def setup_logging():
    """Set up application logging"""
    log_format = '%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s'
    logging.basicConfig(
        level=logging.DEBUG,
        format=log_format,
        datefmt='%H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.getLogger('PyQt6').setLevel(logging.WARNING)
    
    logger = logging.getLogger('MAIN')
    return logger


class SingleApplication(QApplication):
    """Ensures only one instance of the application runs using QLockFile.

    This avoids stale shared memory segments that can block restarts after crashes.
    """

    def __init__(self, argv, key: str):
        super().__init__(argv)
        self._key = key
        self._running = False
        self._lock = None
        self._cleanup_registered = False
        self.logger = logging.getLogger('SingleApp')

        # Prepare a per-user lock file in a writable location
        # PyQt6 nests enums: use StandardLocation; fall back for older Qt
        base_dir = ""
        try:
            base_dir = QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppConfigLocation
            )
        except AttributeError:
            # Older Qt may not have AppConfigLocation
            pass
        if not base_dir:
            try:
                base_dir = QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.AppLocalDataLocation
                )
            except Exception:
                base_dir = ""
        if not base_dir:
            base_dir = QDir.tempPath()
        dir_obj = QDir(base_dir)
        if not dir_obj.exists():
            dir_obj.mkpath(".")

        # Use a clear, app-specific lock file name
        lock_path = dir_obj.filePath("bindkit.lock")
        self._lock = QLockFile(lock_path)
        # Consider old locks stale to recover quickly after crashes
        self._lock.setStaleLockTime(10000)  # 10 seconds

        # Try to acquire lock immediately; if it fails, another instance is active
        if not self._lock.tryLock(0):
            # Try to clear a stale lock left by an abnormal termination
            try:
                self._lock.removeStaleLockFile()
            except Exception as e:
                self.logger.debug(f"Could not remove stale lock file: {e}")
            # Try again after removing a stale lock
            if not self._lock.tryLock(0):
                self._running = True
            else:
                self._running = False
        else:
            self._running = False

        # Ensure we release the lock on normal app quit
        try:
            self.aboutToQuit.connect(self._cleanup_lock)
        except (TypeError, RuntimeError) as e:
            self.logger.warning(f"Could not connect cleanup signal: {e}")

        # Also register a process-exit handler as a best-effort cleanup
        try:
            if not self._cleanup_registered:
                atexit.register(self._cleanup_lock)
                self._cleanup_registered = True
        except Exception as e:
            self.logger.warning(f"Could not register atexit cleanup: {e}")

        # Attempt to handle common termination signals for graceful cleanup
        for sig in (getattr(signal, 'SIGINT', None), getattr(signal, 'SIGTERM', None)):
            if sig is None:
                continue
            try:
                signal.signal(sig, self._handle_signal)
            except Exception:
                # On some platforms, setting handlers may fail; ignore
                pass

    def is_running(self) -> bool:
        return self._running

    def ensure_single_instance(self, enabled: bool) -> None:
        """Honor user setting by enabling/disabling the lock guard at runtime."""
        if not enabled:
            # Release lock so multiple instances can run when setting is disabled
            try:
                if self._lock and self._lock.isLocked():
                    self._lock.unlock()
            except Exception as e:
                self.logger.warning(f"Could not release lock: {e}")
            self._running = False

    def __del__(self):
        self._cleanup_lock()

    def _cleanup_lock(self):
        try:
            if self._lock and self._lock.isLocked():
                self._lock.unlock()
        except Exception as e:
            self.logger.debug(f"Could not unlock during cleanup: {e}")

    def _handle_signal(self, signum, frame):
        # Best-effort cleanup on termination signals
        try:
            self._cleanup_lock()
        finally:
            # Exit immediately to respect the signal
            os._exit(0)


class MVCApplication:
    """
    Main application class that coordinates the MVC architecture.
    
    This class sets up the Model-View-Controller components and
    manages their lifecycle and interconnections.
    """
    
    def __init__(self, scripts_directory: str = "scripts"):
        self.scripts_directory = scripts_directory
        self.logger = logging.getLogger('MVC.App')

        # MVC Components
        self.app_controller = None
        self.script_controller = None
        self.tray_controller = None
        self.main_view = None
        self.tray_view = None
        self.hotkey_manager = None
        self.memory_monitor = None
        # Models
        self._script_execution = None
        # Singleton settings dialog/controller
        self._settings_view = None
        self._settings_controller = None
        self._settings_opening = False
        self._settings_mutex = QMutex()  # Thread-safe access to settings dialog state
        self._settings_manager = None

        # Track failed hotkey registrations for user notification
        self._failed_hotkey_registrations = {}  # script_name -> error_message
        
    def initialize(self):
        """Initialize all MVC components and set up connections"""
        self.logger.info("Initializing MVC application...")
        
        # Initialize memory monitoring
        try:
            self.memory_monitor = get_memory_monitor()
            self.memory_monitor.set_baseline()
            self.logger.info("Memory monitoring initialized")
        except Exception as e:
            self.logger.warning(f"Memory monitoring not available: {e}")
            self.memory_monitor = None
        
        try:
            # Create main application controller (creates all models)
            self.app_controller = AppController(self.scripts_directory)
            
            # Create specialized controllers
            self._create_controllers()
            
            # Create views
            self._create_views()
            
            # Set up MVC connections
            self._setup_mvc_connections()
            
            # Set up hotkey management
            self._setup_hotkey_management()
            
            # Initialize application
            self.app_controller.initialize_application()
            
            # Apply initial theme
            self._apply_initial_theme()
            
            # Log initial memory usage
            if self.memory_monitor:
                memory_stats = self.memory_monitor.get_summary()
                self.logger.info(f"Initial memory usage: {memory_stats.get('current_memory_mb', 0):.2f} MB")
            
            self.logger.info("MVC application initialization complete")
            
        except Exception as e:
            self.logger.error(f"Error during MVC initialization: {e}")
            raise

    def _apply_initial_theme(self):
        """Apply the configured theme on startup."""
        try:
            # We need to access settings directly since controllers might not be fully wired for this yet
            # or we just want to ensure it happens early.
            if not self._settings_manager:
                self._settings_manager = SettingsManager()
            
            theme_manager = ThemeManager()

            preferred = self._settings_manager.get('appearance/theme', 'Slate')

            # Get font/padding settings
            font_size = self._settings_manager.get('appearance/font_size', 11)
            padding_scale = self._settings_manager.get('appearance/padding_scale', 1.0)

            effective = theme_manager.resolve_effective_theme(preferred)
            theme_manager.apply_theme(
                effective,
                font_size=font_size,
                padding_scale=padding_scale
            )
            self.logger.info(f"Initial theme applied: {effective}")
            
        except Exception as e:
            self.logger.error(f"Failed to apply initial theme: {e}")

    def finalize_startup(self):
        """Complete application startup"""
        self.app_controller.finalize_startup()

        # Show notification about failed hotkeys after startup is complete
        if self._failed_hotkey_registrations:
            self._show_hotkey_failures_notification()
    
    def shutdown(self):
        """Shutdown the application gracefully"""
        # Log memory stats before shutdown
        if self.memory_monitor:
            final_stats = self.memory_monitor.get_summary()
            self.logger.info(f"Final memory usage: {final_stats.get('current_memory_mb', 0):.2f} MB")
            comparison = self.memory_monitor.compare_to_baseline()
            self.logger.info(f"Memory growth: {comparison.get('memory_change_mb', 0):.2f} MB")
            
            if final_stats.get('potential_leak', False):
                self.logger.warning("Potential memory leak detected during session")
                leak_info = self.memory_monitor.detect_potential_leaks()
                self.logger.warning(f"Leak details: {leak_info}")
        self.logger.info("Shutting down MVC application...")
        
        try:
            # Disconnect all signals first to prevent issues during cleanup
            self._disconnect_all_signals()
            
            # Clean up hotkey manager
            if self.hotkey_manager:
                self.hotkey_manager.stop()
            
            # Clean up views
            if self.tray_view:
                self.tray_view.cleanup()
            
            # Clean up controllers and models
            if self.tray_controller:
                try:
                    self.tray_controller.blockSignals(True)
                except (TypeError, RuntimeError, AttributeError) as e:
                    self.logger.debug(f"Could not block tray controller signals: {e}")

            if self.script_controller:
                try:
                    self.script_controller.blockSignals(True)
                except (TypeError, RuntimeError, AttributeError) as e:
                    self.logger.debug(f"Could not block script controller signals: {e}")
            
            # Shutdown application
            if self.app_controller:
                self.app_controller.shutdown_application()
                
            self.logger.info("MVC application shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    def _create_controllers(self):
        """Create all controller instances"""
        self.logger.debug("Creating controllers...")

        # Get models from app controller
        script_collection = self.app_controller.get_script_collection_model()
        script_execution = self.app_controller.get_script_execution_model()
        hotkey_model = self.app_controller.get_hotkey_model()
        tray_model = self.app_controller.get_tray_model()
        notification_model = self.app_controller.get_notification_model()

        # Reuse the shared settings manager so we can observe appearance updates.
        try:
            self._settings_manager = script_collection._settings
        except AttributeError:
            self._settings_manager = None

        # Store script execution model for later access
        self._script_execution = script_execution

        # Create script controller
        self.script_controller = ScriptController(
            script_collection, script_execution, hotkey_model
        )

        # Create tray controller
        self.tray_controller = TrayController(
            tray_model, notification_model, self.script_controller
        )

        # Register controllers with app controller
        self.app_controller.set_script_controller(self.script_controller)
        self.app_controller.set_tray_controller(self.tray_controller)

        self.logger.debug("Controllers created")
    
    def _create_views(self):
        """Create all view instances"""
        self.logger.debug("Creating views...")
        
        # Create main view (hidden parent window)
        self.main_view = MainView()
        
        # Create tray view
        self.tray_view = TrayView(self.main_view)
        
        self.logger.debug("Views created")
    
    def _setup_mvc_connections(self):
        """Set up the MVC signal/slot connections"""
        self.logger.debug("Setting up MVC connections...")
        
        # Tray Controller -> Tray View connections
        self.tray_controller.menu_structure_updated.connect(
            self.tray_view.update_menu_structure
        )
        self.tray_controller.notification_display_requested.connect(
            self.tray_view.show_notification
        )
        self.tray_controller.launcher_update_requested.connect(
            self._update_launcher
        )

        # Tray View -> Tray Controller connections
        self.tray_view.menu_action_triggered.connect(
            self.tray_controller.handle_menu_action
        )
        self.tray_view.title_clicked.connect(
            self.tray_controller.handle_title_clicked
        )
        self.tray_view.exit_requested.connect(
            self.tray_controller.handle_exit_requested
        )
        
        # Application-level connections
        self.tray_controller.application_exit_requested.connect(
            self._handle_exit_request
        )
        self.tray_controller.settings_dialog_requested.connect(
            self._handle_settings_request
        )

        # Model -> View connections for tray basics
        tray_model = self.app_controller.get_tray_model()
        tray_model.icon_visibility_changed.connect(
            lambda visible: (self.tray_view.show_icon() if visible else self.tray_view.hide_icon())
        )
        tray_model.tooltip_changed.connect(self.tray_view.set_tooltip)
        
        # Initialize tray view based on models
        self._initialize_view_states()

        # React to appearance changes so tray theming stays current.
        if self._settings_manager:
            try:
                self._settings_manager.settings_changed.connect(self._handle_setting_changed)
            except (TypeError, RuntimeError, AttributeError) as err:
                self.logger.debug(f"Could not connect settings changed handler: {err}")
        
        self.logger.debug("MVC connections setup complete")
    
    def _setup_hotkey_management(self):
        """Set up hotkey management system"""
        self.logger.debug("Setting up hotkey management...")

        try:
            # Create hotkey manager
            self.hotkey_manager = HotkeyManager()

            # Connect hotkey triggers to handler that dispatches to appropriate action
            self.hotkey_manager.hotkey_triggered.connect(self._handle_hotkey_triggered)

            # Connect to registration failures to track them for user notification
            self.hotkey_manager.registration_failed.connect(self._on_hotkey_registration_failed)

            # Start hotkey manager
            if not self.hotkey_manager.start():
                self.logger.warning("Hotkey manager failed to start - hotkeys will not work")
                # Show notification about hotkey system failure
                tray_model = self.app_controller.get_tray_model()
                tray_model.show_notification(
                    "Hotkey System Warning",
                    "Failed to initialize hotkey system. Global hotkeys will not work.",
                    QSystemTrayIcon.MessageIcon.Warning
                )
            else:
                self.logger.info("Hotkey management system started")

                # Register current hotkeys
                self._register_hotkeys()

                # Keep runtime registrations in sync with model changes
                try:
                    hotkey_model = self.app_controller.get_hotkey_model()
                    # When mappings change, refresh all registrations for simplicity
                    hotkey_model.hotkeys_changed.connect(self._refresh_hotkey_registrations)
                except Exception as e:
                    self.logger.warning(f"Failed to connect hotkey change sync: {e}")

        except Exception as e:
            self.logger.error(f"Error setting up hotkey management: {e}")
    
    def _handle_hotkey_triggered(self, script_name: str, hotkey_string: str):
        """Handle hotkey triggers and dispatch to appropriate action"""
        from core.hotkey_manager import SYSTEM_SHOW_MENU

        if script_name == SYSTEM_SHOW_MENU:
            # Show tray menu at screen center
            self.logger.debug(f"System show menu hotkey triggered: {hotkey_string}")
            if self.tray_view:
                self.tray_view.show_menu_at_center()
        else:
            # Execute script
            if self.script_controller:
                self.script_controller.execute_script_from_hotkey(script_name)

    def _on_hotkey_registration_failed(self, script_name: str, hotkey_string: str, error_message: str):
        """Handle hotkey registration failure"""
        self._failed_hotkey_registrations[script_name] = error_message
        self.logger.warning(f"Failed to register hotkey {hotkey_string} for {script_name}: {error_message}")

    def _show_hotkey_failures_notification(self):
        """Show notification about hotkeys that failed to register"""
        try:
            failed_count = len(self._failed_hotkey_registrations)
            if failed_count == 0:
                return

            tray_model = self.app_controller.get_tray_model()

            if failed_count == 1:
                script_name = list(self._failed_hotkey_registrations.keys())[0]
                title = "Hotkey Registration Failed"
                message = f"Could not register hotkey for '{script_name}'.\n\nAnother application may have already registered this hotkey. Try restarting BindKit after closing other applications, or use a different key combination."
            else:
                title = "Multiple Hotkeys Failed"
                message = f"{failed_count} hotkey(s) could not be registered.\n\nAnother application may have already registered these hotkeys. Try restarting BindKit after closing other applications, or use different key combinations.\n\nSee Settings for details."

            tray_model.show_notification(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Warning
            )

        except Exception as e:
            self.logger.error(f"Error showing hotkey failures notification: {e}")

    def validate_all_hotkeys(self) -> dict:
        """
        Validate all registered hotkeys and return their status.

        Returns:
            Dict mapping script_name to status info:
            {
                'script_name': {
                    'hotkey': 'Ctrl+Alt+X',
                    'registered': True/False,
                    'error': 'error message if any'
                }
            }
        """
        if not self.hotkey_manager:
            return {}
        return self.hotkey_manager.validate_registration_status()

    def _register_hotkeys(self):
        """Register all configured hotkeys including system hotkeys"""
        try:
            # Register script hotkeys
            hotkey_mappings = self.script_controller.get_all_hotkeys()

            for script_name, hotkey in hotkey_mappings.items():
                self.hotkey_manager.register_hotkey(script_name, hotkey)
                self.logger.debug(f"Registered hotkey {hotkey} for script {script_name}")

            # Register system show menu hotkey
            from core.hotkey_manager import SYSTEM_SHOW_MENU
            from core.settings import SettingsManager
            settings = SettingsManager()
            show_menu_hotkey = settings.get_show_menu_hotkey()
            if show_menu_hotkey:
                self.hotkey_manager.register_hotkey(SYSTEM_SHOW_MENU, show_menu_hotkey)
                self.logger.debug(f"Registered system show menu hotkey: {show_menu_hotkey}")

        except Exception as e:
            self.logger.error(f"Error registering hotkeys: {e}")

    def _refresh_hotkey_registrations(self):
        """Unregister all and re-register based on current mappings."""
        try:
            if not self.hotkey_manager:
                return
            # Unregister all existing hotkeys
            self.hotkey_manager.unregister_all()
            # Register current set from model
            self._register_hotkeys()
            self.logger.info("Refreshed hotkey registrations to match settings")
        except Exception as e:
            self.logger.error(f"Error refreshing hotkey registrations: {e}")
    
    def _initialize_view_states(self):
        """Initialize view states based on model data"""
        # Show tray icon
        self.tray_view.show_icon()

        # Update tray menu with current scripts
        self.tray_controller.update_menu()

        # Update launcher with current scripts
        self._update_launcher()

    def _update_launcher(self, *args):
        """Update the script launcher with current script data and settings"""
        try:
            # Get script data from controller
            launcher_scripts = self.tray_controller.build_launcher_scripts()

            # Get launcher display settings (with fallback for initialization)
            show_hotkeys = True  # Default
            if hasattr(self, '_settings_controller') and self._settings_controller:
                show_hotkeys = self._settings_controller.get_launcher_show_hotkeys()

            # Update the launcher view
            self.tray_view.update_launcher_scripts(launcher_scripts, show_hotkeys)

            self.logger.debug(f"Launcher updated with {len(launcher_scripts)} scripts, show_hotkeys={show_hotkeys}")
        except Exception as e:
            self.logger.error(f"Error updating launcher: {e}")

    def _handle_setting_changed(self, key, value):
        """React to settings updates that affect the tray view."""
        if not key or not self.tray_view:
            return
        if key.startswith('appearance/'):
            try:
                QTimer.singleShot(0, self.tray_view.refresh_theme)
            except Exception as err:
                self.logger.debug(f"Failed to schedule tray theme refresh for '{key}': {err}")
    
    def _handle_exit_request(self):
        """Handle application exit request"""
        self.logger.info("Application exit requested")
        QApplication.instance().quit()
    
    def _handle_settings_request(self):
        """Handle settings dialog request"""
        self.logger.info("Settings dialog requested")

        # Check for updates when settings dialog is opened
        try:
            update_controller = self.app_controller.get_update_controller()
            if update_controller:
                update_controller.check_for_updates(show_dialog_if_available=True)
        except Exception as e:
            self.logger.debug(f"Update check failed: {e}")

        # Use mutex to ensure thread-safe access to settings dialog state
        self._settings_mutex.lock()

        # If already open or in process, focus existing dialog instead of opening another
        if (self._settings_view is not None and self._settings_view.isVisible()) or self._settings_opening:
            # Capture reference before releasing mutex to prevent race condition
            view_ref = self._settings_view
            self._settings_mutex.unlock()  # Release lock before UI operations
            try:
                if view_ref is not None:
                    # Restore if minimized and bring to front
                    view_ref.setWindowState(
                        view_ref.windowState() & ~Qt.WindowState.WindowMinimized
                    )
                    view_ref.show()
                    # Ensure Presets tab is focused when reopening via tray
                    try:
                        view_ref.select_presets_tab()
                    except (AttributeError, RuntimeError) as e:
                        self.logger.debug(f"Could not select presets tab: {e}")
                    view_ref.raise_()
                    view_ref.activateWindow()
            except (RuntimeError, AttributeError) as e:
                self.logger.warning(f"Could not focus existing settings dialog: {e}")
            return

        # Mark as opening to prevent rapid re-entry creating duplicates
        self._settings_opening = True
        self._settings_mutex.unlock()  # Release lock after setting flag

        # Create settings controller
        self._settings_controller = SettingsController(
            self.app_controller.get_application_model(),
            self.script_controller,
            None  # parent must be a QObject or None
        )

        # Create settings view
        self._settings_view = SettingsView(self.main_view)

        # Populate available themes from theme manager
        try:
            available_themes = self._settings_controller._theme_manager.available_themes()
            self.logger.info(f"Discovered {len(available_themes)} themes: {available_themes}")
            self._settings_view.set_available_themes(available_themes)
        except Exception as e:
            self.logger.warning(f"Failed to load themes: {e}")
            # Fallback to default theme to ensure settings dialog remains usable
            from core.theme_manager import ThemeManager
            self._settings_view.set_available_themes([ThemeManager.DEFAULT_THEME_NAME])

        # Store settings view reference in controller so it can update schedule tab
        self._settings_controller._settings_view = self._settings_view

        # Store mvc_app reference in script controller for hotkey validation
        self.script_controller._mvc_app = self

        # Ensure references are cleared when dialog closes
        self._settings_view.finished.connect(lambda *_: self._teardown_settings_dialog())
        self._settings_view.destroyed.connect(lambda *_: self._teardown_settings_dialog())

        # Wire controller to view
        # View -> Controller connections
        self._settings_view.run_on_startup_changed.connect(self._settings_controller.set_run_on_startup)
        self._settings_view.start_minimized_changed.connect(self._settings_controller.set_start_minimized)
        self._settings_view.show_startup_notification_changed.connect(self._settings_controller.set_show_startup_notification)
        self._settings_view.minimize_to_tray_changed.connect(self._settings_controller.set_minimize_to_tray)
        self._settings_view.close_to_tray_changed.connect(self._settings_controller.set_close_to_tray)
        self._settings_view.single_instance_changed.connect(self._settings_controller.set_single_instance)
        self._settings_view.show_script_notifications_changed.connect(self._settings_controller.set_show_script_notifications)
        self._settings_view.check_for_updates_changed.connect(self._settings_controller.set_check_for_updates)
        self._settings_view.script_timeout_changed.connect(self._settings_controller.set_script_timeout)
        self._settings_view.show_menu_hotkey_config_requested.connect(lambda: self._handle_show_menu_hotkey_config(self._settings_controller))
        self._settings_view.script_toggled.connect(self._settings_controller.toggle_script)
        self._settings_view.custom_name_changed.connect(self._settings_controller.set_script_custom_name)
        self._settings_view.external_script_add_requested.connect(lambda path: self._settings_controller.add_external_script(path))
        self._settings_view.external_script_remove_requested.connect(self._settings_controller.remove_external_script)
        self._settings_view.hotkey_configuration_requested.connect(lambda s: self._handle_hotkey_config(s, self._settings_controller))
        # Add/Edit presets are initiated from Script Args tab
        self._settings_view.add_preset_requested.connect(lambda s: self._handle_preset_editor(s, self._settings_controller))
        self._settings_view.edit_preset_requested.connect(lambda s, p: self._handle_preset_editor(s, self._settings_controller, p))
        # Delete preset from Script Args tab
        def _handle_preset_deletion(display_name, preset):
            # Cache script lookup to avoid calling get_script_by_name twice
            script = self.script_controller._script_collection.get_script_by_name(display_name)
            script_key = script.file_path.stem if script else display_name
            self._settings_controller.delete_script_preset(script_key, preset)

        self._settings_view.preset_deleted.connect(_handle_preset_deletion)
        # Wire Auto-Generate from Script Args tab to controller
        self._settings_view.auto_generate_presets_requested.connect(self._settings_controller.auto_generate_presets)
        # Schedule management connections
        self._settings_view.schedule_enabled_changed.connect(self._settings_controller.set_schedule_enabled)
        self._settings_view.schedule_interval_changed.connect(self._settings_controller.set_schedule_interval)
        self._settings_view.schedule_type_changed.connect(self._settings_controller.set_schedule_type)
        self._settings_view.cron_expression_changed.connect(self._settings_controller.set_cron_expression)
        # Connect schedule view's info request to controller
        self._settings_view.schedule_view.schedule_info_requested.connect(self._settings_controller.on_schedule_info_requested)
        self._settings_view.reset_requested.connect(self._settings_controller.reset_settings)
        self._settings_view.test_all_hotkeys_requested.connect(self._settings_controller.validate_all_hotkeys)
        # Appearance
        self._settings_view.theme_changed.connect(self._settings_controller.set_theme)
        self._settings_view.font_size_changed.connect(self._settings_controller.set_font_size)
        self._settings_view.padding_scale_changed.connect(self._settings_controller.set_padding_scale)
        self._settings_view.launcher_show_hotkeys_changed.connect(self._settings_controller.set_launcher_show_hotkeys)
        # Instant-apply: no accept/save button; models persist on change
        
        # Controller -> View connections
        self._settings_controller.settings_loaded.connect(lambda data: (
            self._settings_view.update_startup_settings(data.get('startup', {})),
            self._settings_view.update_behavior_settings(data.get('behavior', {})),
            self._settings_view.update_execution_settings(data.get('execution', {})),
            self._settings_view.update_script_list(data.get('scripts', [])),
            self._settings_view.set_all_presets(data.get('presets', {}))
        ))
        self._settings_controller.startup_settings_updated.connect(self._settings_view.update_startup_settings)
        self._settings_controller.behavior_settings_updated.connect(self._settings_view.update_behavior_settings)
        self._settings_controller.execution_settings_updated.connect(self._settings_view.update_execution_settings)
        self._settings_controller.script_list_updated.connect(self._settings_view.update_script_list)
        # Update hotkeys incrementally for better UX
        self._settings_controller.hotkey_updated.connect(lambda s, h: self._settings_view.update_script_hotkey(s, h))
        self._settings_controller.show_menu_hotkey_updated.connect(self._settings_view.update_show_menu_hotkey)
        # Refresh hotkey registrations when show menu hotkey changes
        self._settings_controller.show_menu_hotkey_updated.connect(lambda h: self._refresh_hotkey_registrations())
        self._settings_controller.launcher_show_hotkeys_updated.connect(self._settings_view.update_launcher_show_hotkeys)
        self._settings_controller.launcher_show_hotkeys_updated.connect(self._update_launcher)
        self._settings_controller.preset_updated.connect(self._settings_view.update_preset_list)
        self._settings_controller.appearance_settings_updated.connect(self._settings_view.update_appearance_settings)
        # When presets change, refresh tray menu and launcher so preset submenus reflect changes
        try:
            self._settings_controller.preset_updated.connect(lambda *_: self.tray_controller.update_menu())
            self._settings_controller.preset_updated.connect(lambda *_: self._update_launcher())
        except (TypeError, RuntimeError, AttributeError) as e:
            self.logger.warning(f"Could not connect preset_updated signal to tray menu update: {e}")
        # Removed unnecessary confirmation popups for settings_saved and settings_reset
        # Only keep error messages which are important
        self._settings_controller.error_occurred.connect(self._settings_view.show_error)

        # Also refresh the tray menu and launcher when script list metadata changes (e.g., custom names)
        try:
            self._settings_controller.script_list_updated.connect(lambda *_: self.tray_controller.update_menu())
            self._settings_controller.script_list_updated.connect(lambda *_: self._update_launcher())
        except (TypeError, RuntimeError, AttributeError) as e:
            self.logger.warning(f"Could not connect script_list_updated signal to tray menu update: {e}")

        # Connect schedule runtime signals to update UI in real-time
        try:
            schedule_runtime = self._script_execution._script_loader.executor.schedule_runtime
            if schedule_runtime:
                schedule_runtime.schedule_executed.connect(self._settings_controller.on_schedule_executed)
                schedule_runtime.schedule_started.connect(self._settings_controller.on_schedule_started)
                schedule_runtime.schedule_stopped.connect(self._settings_controller.on_schedule_stopped)
                schedule_runtime.schedule_error.connect(self._settings_controller.on_schedule_error)
                schedule_runtime.schedule_execution_blocked.connect(
                    self._settings_controller.on_schedule_execution_blocked
                )
                self._settings_controller._schedule_runtime = schedule_runtime
                self.logger.info("Connected schedule runtime signals to settings controller")
        except (AttributeError, TypeError, RuntimeError) as e:
            self.logger.warning(f"Could not connect schedule runtime signals: {e}")

        # Load current settings
        self._settings_controller.load_all_settings()

        # Open with the Presets tab focused for quicker configuration
        try:
            self._settings_view.select_presets_tab()
        except (AttributeError, RuntimeError) as e:
            self.logger.debug(f"Could not select presets tab: {e}")
        
        # Show dialog
        try:
            self._settings_view.exec()
        finally:
            self.logger.info("Settings dialog closed")
            # Safety cleanup in case finished signal didn't fire
            self._teardown_settings_dialog()

    def _teardown_settings_dialog(self):
        """Release settings dialog/controller resources to prevent leaks."""
        controller = self._settings_controller
        view = self._settings_view

        # Disconnect schedule runtime signals first
        if controller:
            runtime = getattr(controller, '_schedule_runtime', None)
            if runtime:
                connections = (
                    (runtime.schedule_executed, controller.on_schedule_executed),
                    (runtime.schedule_started, controller.on_schedule_started),
                    (runtime.schedule_stopped, controller.on_schedule_stopped),
                    (runtime.schedule_error, controller.on_schedule_error),
                    (runtime.schedule_execution_blocked, controller.on_schedule_execution_blocked),
                )
                for signal_obj, slot in connections:
                    try:
                        signal_obj.disconnect(slot)
                    except (TypeError, RuntimeError):
                        pass

        # Block signals on view before cleanup
        if view:
            try:
                view.blockSignals(True)
            except (TypeError, RuntimeError):
                pass

        # Call cleanup methods to clear resources
        if controller:
            try:
                controller.cleanup()
            except (RuntimeError, AttributeError) as e:
                self.logger.debug(f"Error calling controller cleanup: {e}")

        # Clear references
        self._settings_view = None
        self._settings_controller = None
        self._settings_opening = False

        # Schedule Qt deletion
        if controller:
            try:
                controller.deleteLater()
            except (RuntimeError, AttributeError) as e:
                self.logger.debug(f"Could not delete settings controller: {e}")

        if view:
            try:
                view.deleteLater()
            except (RuntimeError, AttributeError) as e:
                self.logger.debug(f"Could not delete settings view: {e}")

    def _handle_hotkey_config(self, script_name, settings_controller):
        """Handle hotkey configuration dialog"""
        # Get current hotkey for script
        current_hotkey = self.script_controller._hotkey_model.get_hotkey_for_script(script_name)
        
        # Create hotkey config view
        hotkey_view = HotkeyConfigView(script_name, current_hotkey, self.main_view)
        
        # Connect signals
        hotkey_view.hotkey_set.connect(lambda h: settings_controller.set_script_hotkey(script_name, h))
        hotkey_view.hotkey_cleared.connect(lambda: settings_controller.set_script_hotkey(script_name, ""))
        hotkey_view.validation_requested.connect(lambda h: self._validate_hotkey(h, script_name, hotkey_view))
        
        # Show dialog
        hotkey_view.exec()

    def _handle_show_menu_hotkey_config(self, settings_controller):
        """Handle show menu hotkey configuration dialog"""
        # Get current show menu hotkey
        from core.settings import SettingsManager
        settings = SettingsManager()
        current_hotkey = settings.get_show_menu_hotkey()

        # Create hotkey config view
        hotkey_view = HotkeyConfigView("Show Menu", current_hotkey, self.main_view)

        # Connect signals
        hotkey_view.hotkey_set.connect(lambda h: settings_controller.set_show_menu_hotkey(h))
        hotkey_view.hotkey_cleared.connect(lambda: settings_controller.set_show_menu_hotkey(""))
        hotkey_view.validation_requested.connect(lambda h: self._validate_show_menu_hotkey(h, hotkey_view))

        # Show dialog
        hotkey_view.exec()

    def _handle_preset_editor(self, script_name, settings_controller, preset_name: str = None):
        """Handle preset editor dialog for add or edit."""
        # Get script info
        script_info = self.script_controller._script_collection.get_script_by_name(script_name)
        if not script_info:
            return
        
        # Get script arguments
        script_args = []
        if script_info.arguments:
            for arg in script_info.arguments:
                script_args.append({
                    'name': arg.name,
                    'type': arg.type,
                    'help': arg.help,
                    'choices': arg.choices
                })
        
        # Determine initial values for edit vs add
        existing_presets = settings_controller.get_script_presets(script_info.file_path.stem)
        initial_name = preset_name if preset_name else None
        initial_args = existing_presets.get(preset_name, {}) if preset_name else None

        # Create preset editor view (single-preset editor)
        preset_view = PresetEditorView(
            script_name, script_args, self.main_view,
            initial_name=initial_name, initial_args=initial_args
        )
        
        # Connect signals
        def _save_or_rename_preset(new_name, args, _old_name=preset_name, _stem=script_info.file_path.stem):
            try:
                if _old_name and new_name != _old_name:
                    # Rename: delete old then save new
                    settings_controller.delete_script_preset(_stem, _old_name)
                settings_controller.save_script_preset(_stem, new_name, args)
            except Exception:
                # Let controller/view error handling surface to user
                pass

        preset_view.preset_saved.connect(_save_or_rename_preset)
        # Deletion handled from Script Args tab; editor focuses on a single preset
        
        # Show dialog
        preset_view.exec()
    
    def _validate_hotkey(self, hotkey, script_name, hotkey_view):
        """Validate a hotkey and show feedback in view"""
        # Check if hotkey is available
        if not self.script_controller.is_hotkey_available(hotkey, script_name):
            existing_script = self._find_script_with_hotkey(hotkey)
            hotkey_view.show_validation_error(f"Hotkey already assigned to {existing_script}")
            return False
        
        # Check for system hotkeys
        system_hotkeys = [
            'Ctrl+C', 'Ctrl+V', 'Ctrl+X', 'Ctrl+A', 'Ctrl+Z', 'Ctrl+Y',
            'Ctrl+S', 'Ctrl+O', 'Ctrl+N', 'Ctrl+P', 'Ctrl+F',
            'Alt+Tab', 'Alt+F4', 'Win+L', 'Win+D', 'Win+Tab'
        ]
        
        if hotkey in system_hotkeys:
            hotkey_view.show_validation_warning("This hotkey is reserved by the system")
        else:
            hotkey_view.clear_validation()

        return True

    def _validate_show_menu_hotkey(self, hotkey, hotkey_view):
        """Validate the show menu hotkey and show feedback in view"""
        # Check if hotkey conflicts with any script hotkeys
        existing_script = self._find_script_with_hotkey(hotkey)
        if existing_script:
            hotkey_view.show_validation_error(f"Hotkey already assigned to script: {existing_script}")
            return False

        # Check for system hotkeys
        system_hotkeys = [
            'Ctrl+C', 'Ctrl+V', 'Ctrl+X', 'Ctrl+A', 'Ctrl+Z', 'Ctrl+Y',
            'Ctrl+S', 'Ctrl+O', 'Ctrl+N', 'Ctrl+P', 'Ctrl+F',
            'Alt+Tab', 'Alt+F4', 'Win+L', 'Win+D', 'Win+Tab'
        ]

        if hotkey in system_hotkeys:
            hotkey_view.show_validation_warning("This hotkey is reserved by the system")
        else:
            hotkey_view.clear_validation()

        return True
    
    def _find_script_with_hotkey(self, hotkey):
        """Find which script has a specific hotkey assigned"""
        all_hotkeys = self.script_controller._hotkey_model.get_all_hotkeys()
        for script_name, assigned_hotkey in all_hotkeys.items():
            if assigned_hotkey == hotkey:
                return script_name
        return None
    
    def _auto_generate_presets(self, script_name, settings_controller, preset_view):
        """Auto-generate presets and update view"""
        settings_controller.auto_generate_presets(script_name)
        
        # Refresh presets in view
        new_presets = settings_controller.get_script_presets(script_name)
        for preset_name, arguments in new_presets.items():
            preset_view.add_preset(preset_name, arguments)

    def _disconnect_all_signals(self):
        """Disconnect all signal connections to prevent issues during shutdown."""
        try:
            self.logger.debug("Disconnecting all signal connections...")
            
            # Disconnect tray controller signals
            if self.tray_controller:
                try:
                    self.tray_controller.menu_structure_updated.disconnect()
                    self.tray_controller.notification_display_requested.disconnect()
                    self.tray_controller.settings_dialog_requested.disconnect()
                    self.tray_controller.application_exit_requested.disconnect()
                except (TypeError, RuntimeError, AttributeError) as e:
                    self.logger.debug(f"Tray controller signals already disconnected or not connected: {e}")

            # Disconnect tray view signals
            if self.tray_view:
                try:
                    self.tray_view.menu_action_triggered.disconnect()
                    self.tray_view.title_clicked.disconnect()
                    self.tray_view.exit_requested.disconnect()
                except (TypeError, RuntimeError, AttributeError) as e:
                    self.logger.debug(f"Tray view signals already disconnected or not connected: {e}")

            # Disconnect hotkey manager signals
            if self.hotkey_manager:
                try:
                    self.hotkey_manager.hotkey_triggered.disconnect()
                except (TypeError, RuntimeError, AttributeError) as e:
                    self.logger.debug(f"Hotkey manager signals already disconnected or not connected: {e}")

            # Disconnect model signals from controllers
            if self.app_controller:
                try:
                    # Get models and disconnect their signals
                    tray_model = self.app_controller.get_tray_model()
                    if tray_model:
                        tray_model.icon_visibility_changed.disconnect()
                        tray_model.tooltip_changed.disconnect()
                        tray_model.menu_update_requested.disconnect()
                        tray_model.notification_requested.disconnect()

                    script_execution = self.app_controller.get_script_execution_model()
                    if script_execution:
                        script_execution.script_execution_started.disconnect()
                        script_execution.script_execution_completed.disconnect()
                        script_execution.script_execution_failed.disconnect()

                    hotkey_model = self.app_controller.get_hotkey_model()
                    if hotkey_model:
                        hotkey_model.hotkeys_changed.disconnect()

                except (TypeError, RuntimeError, AttributeError) as e:
                    self.logger.debug(f"Model signals already disconnected or not connected: {e}")

            if self._settings_manager:
                try:
                    self._settings_manager.settings_changed.disconnect()
                except (TypeError, RuntimeError, AttributeError) as e:
                    self.logger.debug(f"Settings manager signals already disconnected or not connected: {e}")
                    
            self.logger.debug("Signal disconnection completed")
            
        except Exception as e:
            self.logger.warning(f"Error disconnecting signals: {e}")


def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='BindKit')
    parser.add_argument('--minimized', action='store_true', 
                       help='Start minimized to system tray')
    args = parser.parse_args()
    
    # Change to script directory to ensure correct working directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    logger = setup_logging()
    
    logger.info("="*60)
    logger.info("DESKTOP UTILITY GUI STARTING (MVC Architecture)")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Command line args: {sys.argv}")
    logger.info("="*60)

    # Set High DPI policy BEFORE creating QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application with single-instance support
    app = None
    app = SingleApplication(sys.argv, 'BindKit-SingleInstance')
    
    # Set application identity before accessing QSettings
    app.setApplicationName("BindKit")
    app.setOrganizationName("DesktopUtils")
    
    # Honor the user's single-instance setting
    try:
        from core.settings import SettingsManager
        settings = SettingsManager()
        single_instance_enabled = settings.get('behavior/single_instance', True)
        # Adjust lock behavior to match setting
        app.ensure_single_instance(single_instance_enabled)
        if single_instance_enabled and app.is_running():
            logger.warning("Another instance is already running. Exiting.")
            QMessageBox.information(
                None,
                "Already Running",
                "BindKit is already running in the system tray."
            )
            sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to check single-instance setting: {e}")
    
    # Check if system tray is available
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.error("System tray is not available on this system")
        QMessageBox.critical(None, "System Tray Not Available",
                           "System tray is required but not available on this system.")
        sys.exit(1)

    app.setStyle("Fusion")
    logger.info(f"Application style set to: Fusion")

    # Theme handling: load and apply from settings with safe fallback
    theme_manager = ThemeManager()
    try:
        from core.settings import SettingsManager
        theme_settings = SettingsManager()

        def _apply_theme_from_settings():
            try:
                preferred = theme_settings.get('appearance/theme', ThemeManager.DEFAULT_THEME_NAME)
                effective = theme_manager.resolve_effective_theme(preferred)
                font_pref = theme_settings.get('appearance/font_size', 11)
                padding_pref = theme_settings.get('appearance/padding_scale', 1.0)
                try:
                    font_pref = int(font_pref)
                except (TypeError, ValueError):
                    font_pref = None
                try:
                    padding_pref = float(padding_pref)
                except (TypeError, ValueError):
                    padding_pref = None

                theme_manager.apply_theme(
                    effective,
                    font_size=font_pref,
                    padding_scale=padding_pref
                )
                logger.info(
                    "Theme applied "
                    f"(preferred={preferred}, effective={effective}, "
                    f"font={font_pref}, padding={padding_pref})"
                )
            except Exception as e_inner:
                logger.error(f"Theme application failed: {e_inner}")

        # Apply at startup
        _apply_theme_from_settings()

        # React to settings changes for instant-apply
        def _on_setting_changed(key: str, value):
            if key.startswith('appearance/'):
                _apply_theme_from_settings()

        try:
            theme_settings.settings_changed.connect(_on_setting_changed)
        except Exception as conn_err:
            logger.debug(f"Could not connect theme change handler: {conn_err}")

    except Exception as e:
        logger.error(f"Failed to initialize theme system: {e}")
    
    # Don't quit when last window closes (we have tray icon)
    app.setQuitOnLastWindowClosed(False)
    
    # Create and initialize MVC application
    mvc_app = MVCApplication()
    
    try:
        # Initialize MVC components
        mvc_app.initialize()
        
        # Complete startup
        mvc_app.finalize_startup()
        
        logger.info("Starting application event loop...")
        logger.info("-"*60)
        
        # Run application
        exit_code = app.exec()
        
        # Clean shutdown
        mvc_app.shutdown()
        
        sys.exit(exit_code)
        
    except Exception as e:
        logger.error(f"Fatal error during application startup: {e}")
        QMessageBox.critical(
            None, 
            "Startup Error",
            f"Failed to start application: {str(e)}\n\nCheck the logs for details."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
