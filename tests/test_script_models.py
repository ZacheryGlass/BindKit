"""
Unit tests for Script Models.

These tests validate that the script-related models work correctly
without any UI dependencies.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import QObject, QCoreApplication
from PyQt6.QtTest import QSignalSpy
from models.script_models import ScriptCollectionModel, ScriptExecutionModel, HotkeyModel


class TestScriptCollectionModel(unittest.TestCase):
    """Test cases for ScriptCollectionModel"""
    
    @classmethod
    def setUpClass(cls):
        """Set up QApplication for tests"""
        if not QCoreApplication.instance():
            cls.app = QCoreApplication([])
        else:
            cls.app = QCoreApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        with patch('models.script_models.ScriptLoader') as mock_loader, \
             patch('models.script_models.SettingsManager') as mock_settings:
            
            # Create mock script info objects
            self.mock_script1 = Mock()
            self.mock_script1.display_name = "Test Script 1"
            self.mock_script1.file_path = Mock()
            self.mock_script1.file_path.stem = "test_script_1"
            
            self.mock_script2 = Mock()
            self.mock_script2.display_name = "Test Script 2"
            self.mock_script2.file_path = Mock()
            self.mock_script2.file_path.stem = "test_script_2"
            
            # Configure mock loader
            mock_loader_instance = Mock()
            mock_loader_instance.discover_scripts.return_value = [self.mock_script1, self.mock_script2]
            mock_loader_instance.refresh_external_scripts.return_value = []
            mock_loader.return_value = mock_loader_instance
            
            # Configure mock settings
            mock_settings_instance = Mock()
            mock_settings_instance.get_disabled_scripts.return_value = []
            mock_settings_instance.get_external_scripts.return_value = {}
            mock_settings.return_value = mock_settings_instance
            
            self.model = ScriptCollectionModel("test_scripts")
            self.mock_loader = mock_loader_instance
            self.mock_settings = mock_settings_instance
    
    def test_initialization(self):
        """Test model initializes correctly"""
        self.assertIsNotNone(self.model._script_loader)
        self.assertIsNotNone(self.model._settings)
        self.assertEqual(len(self.model._all_scripts), 0)
        self.assertEqual(len(self.model._available_scripts), 0)
    
    def test_script_discovery(self):
        """Test script discovery functionality"""
        # Set up signal spy
        discovered_spy = QSignalSpy(self.model.scripts_discovered)
        filtered_spy = QSignalSpy(self.model.scripts_filtered)
        
        # Discover scripts
        scripts = self.model.discover_scripts()
        
        # Verify discovery was called
        self.mock_loader.discover_scripts.assert_called_once()
        
        # Check results
        self.assertEqual(len(scripts), 2)
        self.assertEqual(len(discovered_spy), 1)
        self.assertEqual(len(filtered_spy), 1)
        
        # Check internal state
        self.assertEqual(len(self.model._all_scripts), 2)
        self.assertEqual(len(self.model._available_scripts), 2)
    
    def test_script_filtering(self):
        """Test script filtering by disabled status"""
        # Set up disabled scripts
        self.mock_settings.get_disabled_scripts.return_value = ["Test Script 1"]
        
        # Discover scripts
        scripts = self.model.discover_scripts()
        
        # Should only get one script (the non-disabled one)
        self.assertEqual(len(scripts), 1)
        self.assertEqual(scripts[0].display_name, "Test Script 2")
    
    def test_get_script_by_name(self):
        """Test getting script by name"""
        # First discover scripts
        self.model.discover_scripts()
        
        # Test getting existing script
        script = self.model.get_script_by_name("Test Script 1")
        self.assertIsNotNone(script)
        self.assertEqual(script.display_name, "Test Script 1")
        
        # Test getting non-existent script
        script = self.model.get_script_by_name("Non-existent Script")
        self.assertIsNone(script)
    
    def test_enable_disable_script(self):
        """Test enabling and disabling scripts"""
        # Set up signal spies
        enabled_spy = QSignalSpy(self.model.script_enabled)
        disabled_spy = QSignalSpy(self.model.script_disabled)
        
        # Discover scripts first
        self.model.discover_scripts()
        
        # Test disabling script
        self.model.disable_script("Test Script 1")
        
        # Check signal was emitted
        self.assertEqual(len(disabled_spy), 1)
        self.assertEqual(disabled_spy[0][0], "Test Script 1")
        
        # Verify settings call
        self.mock_settings.add_disabled_script.assert_called_with("Test Script 1")
        
        # First add to disabled set to test enabling
        self.model._disabled_scripts.add("Test Script 1")
        
        # Test enabling script
        self.model.enable_script("Test Script 1")
        
        # Check signal was emitted
        self.assertEqual(len(enabled_spy), 1)
        self.assertEqual(enabled_spy[0][0], "Test Script 1")
        
        # Verify settings call
        self.mock_settings.remove_disabled_script.assert_called_with("Test Script 1")


class TestScriptExecutionModel(unittest.TestCase):
    """Test cases for ScriptExecutionModel"""
    
    @classmethod
    def setUpClass(cls):
        """Set up QApplication for tests"""
        if not QCoreApplication.instance():
            cls.app = QCoreApplication([])
        else:
            cls.app = QCoreApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        # Create mock script collection
        self.mock_collection = Mock()
        
        # Create mock script info
        self.mock_script = Mock()
        self.mock_script.display_name = "Test Script"
        self.mock_script.file_path = Mock()
        self.mock_script.file_path.stem = "test_script"
        
        self.mock_collection.get_script_by_name.return_value = self.mock_script
        self.mock_collection.is_external_script.return_value = False
        
        # Mock script loader
        self.mock_collection._script_loader = Mock()
        self.mock_collection._script_loader.execute_script.return_value = {
            'success': True,
            'message': 'Test execution successful'
        }
        
        with patch('models.script_models.SettingsManager') as mock_settings:
            mock_settings_instance = Mock()
            mock_settings_instance.get_status_refresh_seconds.return_value = 5
            mock_settings.return_value = mock_settings_instance
            
            self.model = ScriptExecutionModel(self.mock_collection)
            self.mock_settings = mock_settings_instance
    
    def test_initialization(self):
        """Test model initializes correctly"""
        self.assertIsNotNone(self.model._script_collection)
        self.assertIsNotNone(self.model._script_loader)
        self.assertIsNotNone(self.model._settings)
        self.assertEqual(len(self.model._execution_results), 0)
    
    def test_script_execution_success(self):
        """Test successful script execution"""
        # Set up signal spies
        started_spy = QSignalSpy(self.model.script_execution_started)
        completed_spy = QSignalSpy(self.model.script_execution_completed)
        failed_spy = QSignalSpy(self.model.script_execution_failed)

        # Execute script synchronously (not async) for test predictability
        result = self.model.execute_script("Test Script", async_execution=False)

        # Check result
        self.assertTrue(result)

        # Check signals
        self.assertEqual(len(started_spy), 1)
        self.assertEqual(len(completed_spy), 1)
        self.assertEqual(len(failed_spy), 0)
        
        # Check signal data
        self.assertEqual(started_spy[0][0], "Test Script")
        self.assertEqual(completed_spy[0][0], "Test Script")
        
        # Check execution result was stored
        stored_result = self.model.get_last_execution_result("Test Script")
        self.assertIsNotNone(stored_result)
        self.assertTrue(stored_result['success'])
    
    def test_script_execution_failure(self):
        """Test failed script execution"""
        # Configure mock to return failure
        self.mock_collection._script_loader.execute_script.return_value = {
            'success': False,
            'message': 'Test execution failed'
        }

        # Set up signal spies
        started_spy = QSignalSpy(self.model.script_execution_started)
        completed_spy = QSignalSpy(self.model.script_execution_completed)
        failed_spy = QSignalSpy(self.model.script_execution_failed)

        # Execute script synchronously (not async) for test predictability
        result = self.model.execute_script("Test Script", async_execution=False)

        # Check result
        self.assertFalse(result)

        # Check signals
        self.assertEqual(len(started_spy), 1)
        self.assertEqual(len(completed_spy), 0)
        self.assertEqual(len(failed_spy), 1)
        
        # Check signal data
        self.assertEqual(failed_spy[0][0], "Test Script")
        self.assertEqual(failed_spy[0][1], 'Test execution failed')
    
    def test_script_not_found(self):
        """Test execution of non-existent script"""
        # Configure mock to return None
        self.mock_collection.get_script_by_name.return_value = None
        
        # Set up signal spy
        failed_spy = QSignalSpy(self.model.script_execution_failed)
        
        # Execute script
        result = self.model.execute_script("Non-existent Script")
        
        # Check result
        self.assertFalse(result)
        
        # Check failure signal
        self.assertEqual(len(failed_spy), 1)
        self.assertEqual(failed_spy[0][0], "Non-existent Script")


class TestHotkeyModel(unittest.TestCase):
    """Test cases for HotkeyModel"""
    
    @classmethod
    def setUpClass(cls):
        """Set up QApplication for tests"""
        if not QCoreApplication.instance():
            cls.app = QCoreApplication([])
        else:
            cls.app = QCoreApplication.instance()
    
    def setUp(self):
        """Set up test fixtures"""
        with patch('models.script_models.SettingsManager') as mock_settings, \
             patch('models.script_models.HotkeyRegistry') as mock_registry:
            
            # Configure mocks
            mock_settings_instance = Mock()
            mock_settings.return_value = mock_settings_instance
            
            mock_registry_instance = Mock()
            mock_registry_instance.get_all_mappings.return_value = {
                "Test Script": "Ctrl+Alt+T"
            }
            mock_registry.return_value = mock_registry_instance
            
            self.model = HotkeyModel()
            self.mock_settings = mock_settings_instance
            self.mock_registry = mock_registry_instance
    
    def test_initialization(self):
        """Test model initializes correctly"""
        self.assertIsNotNone(self.model._settings)
        self.assertIsNotNone(self.model._hotkey_registry)
        
        # Check that hotkeys were loaded
        self.assertEqual(len(self.model._script_hotkeys), 1)
        self.assertEqual(self.model._script_hotkeys["Test Script"], "Ctrl+Alt+T")
    
    def test_get_hotkey_for_script(self):
        """Test getting hotkey for a script"""
        hotkey = self.model.get_hotkey_for_script("Test Script")
        self.assertEqual(hotkey, "Ctrl+Alt+T")
        
        # Test non-existent script
        hotkey = self.model.get_hotkey_for_script("Non-existent Script")
        self.assertIsNone(hotkey)
    
    def test_set_hotkey_for_script(self):
        """Test setting hotkey for a script"""
        # Set up signal spies
        registered_spy = QSignalSpy(self.model.hotkey_registered)
        changed_spy = QSignalSpy(self.model.hotkeys_changed)
        failed_spy = QSignalSpy(self.model.hotkey_registration_failed)
        
        # Configure mock to succeed
        self.mock_registry.add_hotkey.return_value = (True, "")
        
        # Set hotkey
        self.model.set_hotkey_for_script("New Script", "Ctrl+Shift+N")
        
        # Check registry was called
        self.mock_registry.add_hotkey.assert_called_with("New Script", "Ctrl+Shift+N")
        
        # Check signals
        self.assertEqual(len(registered_spy), 1)
        self.assertEqual(len(changed_spy), 1)
        self.assertEqual(len(failed_spy), 0)
        
        # Check local cache was updated
        self.assertEqual(self.model._script_hotkeys["New Script"], "Ctrl+Shift+N")
    
    def test_set_hotkey_failure(self):
        """Test setting hotkey failure"""
        # Set up signal spy
        failed_spy = QSignalSpy(self.model.hotkey_registration_failed)
        
        # Configure mock to fail
        self.mock_registry.add_hotkey.return_value = (False, "Hotkey already assigned")
        
        # Set hotkey
        self.model.set_hotkey_for_script("New Script", "Ctrl+Shift+N")
        
        # Check failure signal
        self.assertEqual(len(failed_spy), 1)
        self.assertEqual(failed_spy[0][0], "New Script")
        self.assertEqual(failed_spy[0][1], "Ctrl+Shift+N")
        self.assertEqual(failed_spy[0][2], "Hotkey already assigned")
    
    def test_remove_hotkey_for_script(self):
        """Test removing hotkey for a script"""
        # Set up signal spies
        unregistered_spy = QSignalSpy(self.model.hotkey_unregistered)
        changed_spy = QSignalSpy(self.model.hotkeys_changed)
        
        # Configure mock to succeed
        self.mock_registry.remove_hotkey.return_value = True
        
        # Remove hotkey
        self.model.remove_hotkey_for_script("Test Script")
        
        # Check registry was called
        self.mock_registry.remove_hotkey.assert_called_with("Test Script")
        
        # Check signals
        self.assertEqual(len(unregistered_spy), 1)
        self.assertEqual(len(changed_spy), 1)
        
        # Check local cache was updated
        self.assertNotIn("Test Script", self.model._script_hotkeys)
    
    def test_is_hotkey_available(self):
        """Test checking hotkey availability"""
        # Configure mock
        self.mock_registry.get_script_for_hotkey.return_value = None
        
        # Test available hotkey
        available = self.model.is_hotkey_available("Ctrl+Alt+X")
        self.assertTrue(available)
        
        # Configure mock to return existing script
        self.mock_registry.get_script_for_hotkey.return_value = "Test Script"
        
        # Test unavailable hotkey
        available = self.model.is_hotkey_available("Ctrl+Alt+T")
        self.assertFalse(available)
        
        # Test with exclusion (same script)
        available = self.model.is_hotkey_available("Ctrl+Alt+T", "Test Script")
        self.assertTrue(available)


if __name__ == '__main__':
    unittest.main()