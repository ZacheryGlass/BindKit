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
from PyQt6.QtCore import Qt, QLockFile, QDir, QStandardPaths
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
            except Exception:
                pass
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
        except Exception:
            pass

        # Also register a process-exit handler as a best-effort cleanup
        try:
            if not self._cleanup_registered:
                atexit.register(self._cleanup_lock)
                self._cleanup_registered = True
        except Exception:
            pass

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
            except Exception:
                pass
            self._running = False

    def __del__(self):
        self._cleanup_lock()

    def _cleanup_lock(self):
        try:
            if self._lock and self._lock.isLocked():
                self._lock.unlock()
        except Exception:
            pass

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
        # Singleton settings dialog/controller
        self._settings_view = None
        self._settings_controller = None
        self._settings_opening = False
        
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
            
            # Log initial memory usage
            if self.memory_monitor:
                memory_stats = self.memory_monitor.get_summary()
                self.logger.info(f"Initial memory usage: {memory_stats.get('current_memory_mb', 0):.2f} MB")
            
            self.logger.info("MVC application initialization complete")
            
        except Exception as e:
            self.logger.error(f"Error during MVC initialization: {e}")
            raise
    
    def finalize_startup(self):
        """Complete application startup"""
        self.app_controller.finalize_startup()
    
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
                except Exception:
                    pass
            
            if self.script_controller:
                try:
                    self.script_controller.blockSignals(True)
                except Exception:
                    pass
            
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
        
        self.logger.debug("MVC connections setup complete")
    
    def _setup_hotkey_management(self):
        """Set up hotkey management system"""
        self.logger.debug("Setting up hotkey management...")

        try:
            # Create hotkey manager
            self.hotkey_manager = HotkeyManager()
            
            # Connect hotkey triggers to script execution
            self.hotkey_manager.hotkey_triggered.connect(
                self.script_controller.execute_script_from_hotkey
            )
            
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
    
    def _register_hotkeys(self):
        """Register all configured hotkeys"""
        try:
            hotkey_mappings = self.script_controller.get_all_hotkeys()
            
            for script_name, hotkey in hotkey_mappings.items():
                self.hotkey_manager.register_hotkey(script_name, hotkey)
                self.logger.debug(f"Registered hotkey {hotkey} for script {script_name}")
                
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
    
    def _handle_exit_request(self):
        """Handle application exit request"""
        self.logger.info("Application exit requested")
        QApplication.instance().quit()
    
    def _handle_settings_request(self):
        """Handle settings dialog request"""
        self.logger.info("Settings dialog requested")

        # If already open or in process, focus existing dialog instead of opening another
        if (self._settings_view is not None and self._settings_view.isVisible()) or self._settings_opening:
            try:
                if self._settings_view is not None:
                    # Restore if minimized and bring to front
                    self._settings_view.setWindowState(
                        self._settings_view.windowState() & ~Qt.WindowState.WindowMinimized
                    )
                    self._settings_view.show()
                    # Ensure Presets tab is focused when reopening via tray
                    try:
                        self._settings_view.select_presets_tab()
                    except Exception:
                        pass
                    self._settings_view.raise_()
                    self._settings_view.activateWindow()
            except Exception:
                pass
            return

        # Mark as opening to prevent rapid re-entry creating duplicates
        self._settings_opening = True

        # Create settings controller
        self._settings_controller = SettingsController(
            self.app_controller.get_application_model(),
            self.script_controller,
            None  # parent must be a QObject or None
        )

        # Create settings view
        self._settings_view = SettingsView(self.main_view)

        # Store settings view reference in controller so it can update schedule tab
        self._settings_controller._settings_view = self._settings_view

        # Ensure references are cleared when dialog closes
        def _cleanup_settings(_=None):
            self._settings_view = None
            self._settings_controller = None

        self._settings_view.finished.connect(_cleanup_settings)
        self._settings_view.destroyed.connect(lambda *_: _cleanup_settings())

        # Wire controller to view
        # View -> Controller connections
        self._settings_view.run_on_startup_changed.connect(self._settings_controller.set_run_on_startup)
        self._settings_view.start_minimized_changed.connect(self._settings_controller.set_start_minimized)
        self._settings_view.show_startup_notification_changed.connect(self._settings_controller.set_show_startup_notification)
        self._settings_view.minimize_to_tray_changed.connect(self._settings_controller.set_minimize_to_tray)
        self._settings_view.close_to_tray_changed.connect(self._settings_controller.set_close_to_tray)
        self._settings_view.single_instance_changed.connect(self._settings_controller.set_single_instance)
        self._settings_view.show_script_notifications_changed.connect(self._settings_controller.set_show_script_notifications)
        self._settings_view.script_timeout_changed.connect(self._settings_controller.set_script_timeout)
        self._settings_view.script_toggled.connect(self._settings_controller.toggle_script)
        self._settings_view.custom_name_changed.connect(self._settings_controller.set_script_custom_name)
        self._settings_view.external_script_add_requested.connect(lambda path: self._settings_controller.add_external_script(path))
        self._settings_view.external_script_remove_requested.connect(self._settings_controller.remove_external_script)
        self._settings_view.hotkey_configuration_requested.connect(lambda s: self._handle_hotkey_config(s, self._settings_controller))
        # Add/Edit presets are initiated from Script Args tab
        self._settings_view.add_preset_requested.connect(lambda s: self._handle_preset_editor(s, self._settings_controller))
        self._settings_view.edit_preset_requested.connect(lambda s, p: self._handle_preset_editor(s, self._settings_controller, p))
        # Delete preset from Script Args tab
        self._settings_view.preset_deleted.connect(
            lambda display_name, preset: self._settings_controller.delete_script_preset(
                (self.script_controller._script_collection.get_script_by_name(display_name).file_path.stem
                 if self.script_controller._script_collection.get_script_by_name(display_name) else display_name),
                preset
            )
        )
        # Wire Auto-Generate from Script Args tab to controller
        self._settings_view.auto_generate_presets_requested.connect(self._settings_controller.auto_generate_presets)
        # Schedule management connections
        self._settings_view.schedule_enabled_changed.connect(self._settings_controller.set_schedule_enabled)
        self._settings_view.schedule_interval_changed.connect(self._settings_controller.set_schedule_interval)
        self._settings_view.run_now_requested.connect(self._settings_controller.run_scheduled_script_now)
        self._settings_view.reset_requested.connect(self._settings_controller.reset_settings)
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
        self._settings_controller.preset_updated.connect(self._settings_view.update_preset_list)
        # When presets change, refresh tray menu so preset submenus reflect changes
        try:
            self._settings_controller.preset_updated.connect(lambda *_: self.tray_controller.update_menu())
        except Exception:
            pass
        # Removed unnecessary confirmation popups for settings_saved and settings_reset
        # Only keep error messages which are important
        self._settings_controller.error_occurred.connect(self._settings_view.show_error)

        # Also refresh the tray menu when script list metadata changes (e.g., custom names)
        try:
            self._settings_controller.script_list_updated.connect(lambda *_: self.tray_controller.update_menu())
        except Exception:
            pass
        
        # Load current settings
        self._settings_controller.load_all_settings()

        # Open with the Presets tab focused for quicker configuration
        try:
            self._settings_view.select_presets_tab()
        except Exception:
            pass
        
        # Show dialog
        try:
            self._settings_view.exec()
        finally:
            self.logger.info("Settings dialog closed")
            # Safety cleanup in case finished signal didn't fire
            self._settings_view = None
            self._settings_controller = None
            self._settings_opening = False
    
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
                except Exception:
                    pass  # Signal might already be disconnected
            
            # Disconnect tray view signals
            if self.tray_view:
                try:
                    self.tray_view.menu_action_triggered.disconnect()
                    self.tray_view.title_clicked.disconnect()
                    self.tray_view.exit_requested.disconnect()
                except Exception:
                    pass
            
            # Disconnect hotkey manager signals
            if self.hotkey_manager:
                try:
                    self.hotkey_manager.hotkey_triggered.disconnect()
                    self.hotkey_manager.registration_failed.disconnect()
                except Exception:
                    pass
            
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
                        
                except Exception:
                    pass
                    
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
    
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app.setStyle("Fusion")
    logger.info(f"Application style set to: Fusion")
    
    # Load and apply custom stylesheet
    try:
        style_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'style.qss')
        if os.path.exists(style_path):
            with open(style_path, 'r', encoding='utf-8') as f:
                app.setStyleSheet(f.read())
            logger.info(f"Applied custom stylesheet: {style_path}")
        else:
            logger.warning(f"Custom stylesheet not found: {style_path}")
    except Exception as e:
        logger.error(f"Failed to load custom stylesheet: {e}")
    
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
