"""
Tray Controller - Manages system tray interactions and menu coordination.

This controller handles tray icon behavior, menu updates, and coordinates
between tray-related models and the tray view.
"""
import logging
from typing import Dict, Any, List
from PyQt6.QtCore import QObject, pyqtSignal

from models.system_models import TrayIconModel, NotificationModel
from controllers.script_controller import ScriptController

logger = logging.getLogger('Controllers.Tray')


class TrayController(QObject):
    """
    Controller for managing system tray interactions.
    
    This controller:
    - Manages tray icon state and visibility
    - Coordinates menu updates based on script changes
    - Handles tray icon interactions
    - Manages tray notifications
    """
    
    # Signals for view updates
    menu_structure_updated = pyqtSignal(dict)  # Menu structure data
    notification_display_requested = pyqtSignal(str, str, object)  # title, message, icon
    launcher_update_requested = pyqtSignal()  # Launcher script data update needed
    settings_dialog_requested = pyqtSignal()
    application_exit_requested = pyqtSignal()

    def __init__(self, tray_model: TrayIconModel,
                 notification_model: NotificationModel,
                 script_controller: ScriptController):
        super().__init__()
        
        self._tray_model = tray_model
        self._notification_model = notification_model
        self._script_controller = script_controller
        
        # Connect model signals
        self._setup_model_connections()
        
        logger.info("TrayController initialized")
    
    # Tray icon management
    def show_tray_icon(self):
        """Show the system tray icon"""
        self._tray_model.show_icon()
    
    def hide_tray_icon(self):
        """Hide the system tray icon"""
        self._tray_model.hide_icon()
    
    def set_tray_tooltip(self, tooltip: str):
        """Set the tray icon tooltip"""
        self._tray_model.set_tooltip(tooltip)
    
    def is_tray_visible(self) -> bool:
        """Check if tray icon is visible"""
        return self._tray_model.is_visible()
    
    # Menu management
    def update_menu(self):
        """Update the tray menu and launcher based on current script state"""
        logger.debug("Updating tray menu and launcher...")

        try:
            available_scripts = self._script_controller.get_available_scripts()
            menu_structure = self._build_menu_structure(available_scripts)
            self.menu_structure_updated.emit(menu_structure)
            logger.debug(f"Menu updated with {len(available_scripts)} scripts")
        except Exception as e:
            logger.error(f"Error updating menu: {e}")
    
    def _build_menu_structure(self, scripts) -> Dict[str, Any]:
        """Build the menu structure data for the view"""
        menu_items = []
        if not scripts:
            menu_items.append({
                'type': 'action',
                'text': 'No scripts available',
                'enabled': False,
                'data': None
            })
        else:
            # First pass: collect all script data and find max name length
            script_data = []
            max_name_length = 0
            
            for script_info in scripts:
                # Use effective display name (respects custom names) for UI text
                effective_name = self._script_controller._script_collection.get_script_display_name(script_info)
                # Use original analyzer display name for model lookups
                original_name = script_info.display_name
                # Status by original name
                status = self._script_controller.get_script_status(original_name)
                # Hotkey lookup uses canonical identifier (falls back internally)
                identifier = getattr(script_info, 'identifier', None)
                lookup_key = identifier or (script_info.file_path.stem if hasattr(script_info, 'file_path') else None)
                hotkey = self._script_controller.get_script_hotkey(lookup_key) if lookup_key else None
                
                # Track max length for scripts with hotkeys
                if hotkey:
                    # Include status in the length calculation if present
                    name_with_status = effective_name
                    if status and status != "Ready":
                        name_with_status += f" [{status}]"
                    max_name_length = max(max_name_length, len(name_with_status))
                
                script_data.append((script_info, effective_name, status, hotkey))
            
            # Second pass: build menu items with aligned formatting
            for script_info, effective_name, status, hotkey in script_data:
                menu_items.append(self._build_script_menu_item(
                    script_info, effective_name, status, hotkey, max_name_length
                ))
        return {
            'title': 'BindKit ⚙️',
            'items': menu_items
        }

    def _build_script_menu_item(self, script_info, display_text: str, status: str, hotkey: str = None, max_name_length: int = 0) -> Dict[str, Any]:
        """Build a menu item for a specific script with aligned hotkey display.

        display_text is the effective (customized) name, while script_info.display_name is the
        original identifier used by models.
        """
        script_name = script_info.display_name  # original name for actions
        
        # Check if script is currently running
        is_running = self._script_controller._script_execution.is_script_running(script_name)
        
        # Build the base display text with status
        if is_running:
            display_text += " [Running...]"
        elif status and status != "Ready":
            display_text += f" [{status}]"
        
        # Format with aligned hotkey if present
        if hotkey and max_name_length > 0:
            # Pad the script name to align the pipe character
            display_text = f"{display_text:<{max_name_length}} | {hotkey}"
        elif hotkey:
            # Fallback if no alignment (shouldn't happen in normal flow)
            display_text += f" ({hotkey})"
        
        # If script is running, allow cancellation
        if is_running:
            return {
                'type': 'action',
                'text': display_text,
                'enabled': True,
                'is_running': True,
                'data': {
                    'action': 'cancel_script',
                    'script_name': script_name,
                    'script_info': script_info
                }
            }
        
        if script_info.arguments:
            # Only show saved presets; no auto-discovery in tray.
            if self._has_preset_configuration(script_name):
                return self._build_preset_submenu_item(script_info, display_text)
            else:
                return {
                    'type': 'action',
                    'text': f"{display_text} (needs config)",
                    'enabled': True,
                    'data': {
                        'action': 'configure_script',
                        'script_name': script_name,
                        'script_info': script_info
                    }
                }
        else:
            return {
                'type': 'action',
                'text': display_text,
                'enabled': True,
                'data': {
                    'action': 'execute_script',
                    'script_name': script_name,
                    'script_info': script_info
                }
            }
    
    def _build_choice_submenu_item(self, script_info, display_text: str) -> Dict[str, Any]:
        """Build submenu for script with choice arguments"""
        # Assume single choice argument for now
        arg_info = script_info.arguments[0]
        submenu_items = []
        for choice in getattr(arg_info, 'choices', []) or []:
            submenu_items.append({
                'type': 'action',
                'text': choice,
                'enabled': True,
                'data': {
                    'action': 'execute_script_with_choice',
                    'script_name': script_info.display_name,
                    'arg_name': arg_info.name,
                    'choice': choice,
                    'script_info': script_info
                }
            })
        return {
            'type': 'submenu',
            'text': display_text,
            'enabled': True,
            'items': submenu_items
        }
    
    def _build_preset_submenu_item(self, script_info, display_text: str) -> Dict[str, Any]:
        """Build submenu for script with saved presets from settings"""
        preset_names = []
        try:
            preset_names = self._script_controller.get_preset_names(script_info.display_name)
        except Exception:
            preset_names = []

        if not preset_names:
            # Fallback to configure action if somehow no presets are returned
            return {
                'type': 'action',
                'text': f"{display_text} (needs config)",
                'enabled': True,
                'data': {
                    'action': 'configure_script',
                    'script_name': script_info.display_name,
                    'script_info': script_info
                }
            }

        submenu_items = []
        for preset in preset_names:
            submenu_items.append({
                'type': 'action',
                'text': preset,
                'enabled': True,
                'data': {
                    'action': 'execute_script_with_preset',
                    'script_name': script_info.display_name,
                    'preset_name': preset,
                    'script_info': script_info
                }
            })

        # Add manage option at the bottom
        submenu_items.append({
            'type': 'separator'
        })
        submenu_items.append({
            'type': 'action',
            'text': 'Manage Presets…',
            'enabled': True,
            'data': {
                'action': 'configure_script',
                'script_name': script_info.display_name,
                'script_info': script_info
            }
        })

        return {
            'type': 'submenu',
            'text': display_text,
            'enabled': True,
            'items': submenu_items
        }
    
    def build_launcher_scripts(self) -> List[Dict[str, Any]]:
        """Build the script data for the launcher widget"""
        launcher_scripts = []

        try:
            available_scripts = self._script_controller.get_available_scripts()

            for script_info in available_scripts:
                # Use effective display name (respects custom names)
                effective_name = self._script_controller._script_collection.get_script_display_name(script_info)
                # Use original analyzer display name for model lookups
                original_name = script_info.display_name
                # Get status
                status = self._script_controller.get_script_status(original_name)
                # Get hotkey
                identifier = getattr(script_info, 'identifier', None)
                lookup_key = identifier or (script_info.file_path.stem if hasattr(script_info, 'file_path') else None)
                hotkey = self._script_controller.get_script_hotkey(lookup_key) if lookup_key else None
                # Check if running
                is_running = self._script_controller._script_execution.is_script_running(original_name)
                # Check if has presets
                has_presets = self._has_preset_configuration(original_name)

                # Build launcher script data
                launcher_scripts.append({
                    'name': effective_name,
                    'original_name': original_name,
                    'hotkey': hotkey or '',
                    'status': status or 'Ready',
                    'is_running': is_running,
                    'has_presets': has_presets,
                    'script_info': script_info
                })

            logger.debug(f"Built launcher data with {len(launcher_scripts)} scripts")
        except Exception as e:
            logger.error(f"Error building launcher scripts: {e}")

        return launcher_scripts

    def _has_preset_configuration(self, script_name: str) -> bool:
        """Check if script has preset configurations"""
        try:
            return self._script_controller.has_presets(script_name)
        except Exception:
            return False

    # User interaction handlers (called by views)
    def handle_menu_action(self, action_data: Dict[str, Any]):
        """Handle a menu action triggered by the user (from menu or launcher)"""
        if not action_data:
            return

        # Check if this is from the launcher (has 'original_name') or menu (has 'action')
        if 'original_name' in action_data:
            # Launcher format - direct script execution
            script_name = action_data.get('original_name')
            is_running = action_data.get('is_running', False)
            has_presets = action_data.get('has_presets', False)

            logger.info(f"Handling launcher action for script: {script_name}")

            if is_running:
                # Cancel running script
                self._script_controller.cancel_script_execution(script_name)
            elif has_presets:
                # For scripts with presets, show settings (user needs to select preset)
                logger.info(f"Script {script_name} has presets - opening settings")
                self.settings_dialog_requested.emit()
            else:
                # Execute script directly
                self._script_controller.execute_script(script_name)
        else:
            # Menu format - has 'action' field
            action = action_data.get('action')
            script_name = action_data.get('script_name')
            logger.info(f"Handling menu action: {action} for script: {script_name}")

            if action == 'execute_script':
                self._script_controller.execute_script(script_name)
            elif action == 'execute_script_with_choice':
                arg_name = action_data.get('arg_name')
                choice = action_data.get('choice')
                self._script_controller.execute_script_with_choice(script_name, arg_name, choice)
            elif action == 'execute_script_with_preset':
                preset_name = action_data.get('preset_name')
                self._script_controller.execute_script_with_preset(script_name, preset_name)
            elif action == 'cancel_script':
                logger.info(f"Script cancellation requested for: {script_name}")
                self._script_controller.cancel_script_execution(script_name)
            elif action == 'configure_script':
                logger.info(f"Script configuration requested for: {script_name}")
                self.settings_dialog_requested.emit()
            else:
                logger.warning(f"Unknown menu action: {action}")
    
    def handle_title_clicked(self):
        """Handle click on menu title (open settings)"""
        logger.info("Tray menu title clicked - opening settings")
        self.settings_dialog_requested.emit()
    
    def handle_exit_requested(self):
        """Handle application exit request from tray"""
        logger.info("Application exit requested from tray")
        self.application_exit_requested.emit()
    
    # Notification handling
    def show_notification(self, title: str, message: str, icon_type=None):
        """Show a tray notification"""
        self._notification_model.show_notification(title, message, icon_type)

    def show_script_notification(self, script_name: str, message: str, success: bool = True):
        """Show a script execution notification"""
        self._notification_model.show_script_notification(script_name, message, success)

    # Model signal handlers
    def _setup_model_connections(self):
        """Set up connections to model signals"""
        logger.debug("Setting up tray controller model connections...")
        self._tray_model.menu_update_requested.connect(self.update_menu)
        self._tray_model.notification_requested.connect(self.notification_display_requested.emit)
        self._script_controller.script_list_updated.connect(lambda scripts: self.update_menu())

        # Connect script execution signals to update menu and launcher for running state
        self._script_controller._script_execution.script_execution_started.connect(
            lambda name: (self.update_menu(), self.launcher_update_requested.emit()))
        self._script_controller._script_execution.script_execution_completed.connect(
            lambda name, result: (self.update_menu(), self.launcher_update_requested.emit()))
        self._script_controller._script_execution.script_execution_failed.connect(
            lambda name, error: (self.update_menu(), self.launcher_update_requested.emit()))

        logger.debug("Tray controller model connections setup complete")
