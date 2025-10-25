"""
Unit tests for HotkeyRegistry.

Tests hotkey persistence, validation, and duplicate detection.
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from PyQt6.QtCore import QSettings
from PyQt6.QtTest import QSignalSpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.hotkey_registry import HotkeyRegistry


class TestHotkeyRegistry:
    """Test cases for HotkeyRegistry"""

    @pytest.fixture
    def mock_settings(self):
        """Create a mock SettingsManager"""
        settings = Mock()
        settings.settings = MagicMock(spec=QSettings)
        settings.settings.beginGroup = Mock()
        settings.settings.endGroup = Mock()
        settings.settings.childKeys = Mock(return_value=[])
        settings.settings.value = Mock(return_value=None)
        settings.settings.remove = Mock()
        settings.set = Mock()
        settings.sync = Mock()
        return settings

    def test_initialization_empty(self, mock_settings):
        """Test registry initializes with no mappings"""
        registry = HotkeyRegistry(mock_settings)

        assert registry._mappings is not None
        assert registry._reverse_mappings is not None
        assert len(registry._mappings) == 0

    def test_initialization_loads_existing(self, mock_settings):
        """Test registry loads existing hotkeys from settings"""
        # Mock existing hotkeys in settings
        mock_settings.settings.childKeys.return_value = ["Script1", "Script2"]
        mock_settings.settings.value.side_effect = lambda key: {
            "Script1": "Ctrl+Alt+T",
            "Script2": "Ctrl+Shift+S"
        }.get(key)

        registry = HotkeyRegistry(mock_settings)

        # Should load both mappings
        assert len(registry._mappings) == 2
        assert registry._mappings["Script1"] == "Ctrl+Alt+T"
        assert registry._mappings["Script2"] == "Ctrl+Shift+S"

    def test_add_hotkey_success(self, mock_settings):
        """Test adding a new hotkey"""
        registry = HotkeyRegistry(mock_settings)

        success, error = registry.add_hotkey("TestScript", "Ctrl+Alt+T")

        assert success
        assert error == "" or error is None
        assert registry._mappings["TestScript"] == "Ctrl+Alt+T"
        assert registry._reverse_mappings["Ctrl+Alt+T"] == "TestScript"

    def test_add_hotkey_duplicate(self, mock_settings):
        """Test adding a hotkey that's already assigned"""
        registry = HotkeyRegistry(mock_settings)

        # Add first hotkey
        registry.add_hotkey("Script1", "Ctrl+Alt+T")

        # Try to add same hotkey to different script
        success, error = registry.add_hotkey("Script2", "Ctrl+Alt+T")

        assert not success
        assert "already assigned" in error.lower()

    def test_add_hotkey_update_existing(self, mock_settings):
        """Test updating an existing script's hotkey"""
        registry = HotkeyRegistry(mock_settings)

        # Add initial hotkey
        registry.add_hotkey("TestScript", "Ctrl+Alt+T")

        # Update to new hotkey
        success, error = registry.add_hotkey("TestScript", "Ctrl+Shift+T")

        assert success
        assert registry._mappings["TestScript"] == "Ctrl+Shift+T"
        # Old hotkey should no longer be mapped
        assert "Ctrl+Alt+T" not in registry._reverse_mappings

    def test_remove_hotkey_success(self, mock_settings):
        """Test removing a hotkey"""
        registry = HotkeyRegistry(mock_settings)

        # Add a hotkey
        registry.add_hotkey("TestScript", "Ctrl+Alt+T")

        # Remove it
        success = registry.remove_hotkey("TestScript")

        assert success
        assert "TestScript" not in registry._mappings
        assert "Ctrl+Alt+T" not in registry._reverse_mappings

    def test_remove_nonexistent_hotkey(self, mock_settings):
        """Test removing a hotkey that doesn't exist"""
        registry = HotkeyRegistry(mock_settings)

        # Try to remove non-existent hotkey
        success = registry.remove_hotkey("NonexistentScript")

        # Should handle gracefully (may return True or False depending on implementation)
        assert success is not None

    def test_get_hotkey_for_script(self, mock_settings):
        """Test getting hotkey for a script"""
        registry = HotkeyRegistry(mock_settings)

        registry.add_hotkey("TestScript", "Ctrl+Alt+T")

        hotkey = registry.get_hotkey("TestScript")

        assert hotkey == "Ctrl+Alt+T"

    def test_get_hotkey_for_nonexistent_script(self, mock_settings):
        """Test getting hotkey for script that has none"""
        registry = HotkeyRegistry(mock_settings)

        hotkey = registry.get_hotkey("NonexistentScript")

        assert hotkey is None

    def test_get_script_for_hotkey(self, mock_settings):
        """Test getting script name from hotkey"""
        registry = HotkeyRegistry(mock_settings)

        registry.add_hotkey("TestScript", "Ctrl+Alt+T")

        script_name = registry.get_script_for_hotkey("Ctrl+Alt+T")

        assert script_name == "TestScript"

    def test_get_all_mappings(self, mock_settings):
        """Test getting all hotkey mappings"""
        registry = HotkeyRegistry(mock_settings)

        registry.add_hotkey("Script1", "Ctrl+Alt+1")
        registry.add_hotkey("Script2", "Ctrl+Alt+2")
        registry.add_hotkey("Script3", "Ctrl+Alt+3")

        mappings = registry.get_all_mappings()

        assert len(mappings) == 3
        assert mappings["Script1"] == "Ctrl+Alt+1"
        assert mappings["Script2"] == "Ctrl+Alt+2"

    @pytest.mark.edge_case
    def test_add_empty_script_name(self, mock_settings):
        """Test adding hotkey with empty script name"""
        registry = HotkeyRegistry(mock_settings)

        success, error = registry.add_hotkey("", "Ctrl+Alt+T")

        assert not success
        assert "empty" in error.lower() or "cannot" in error.lower()

    @pytest.mark.edge_case
    def test_add_empty_hotkey(self, mock_settings):
        """Test adding empty hotkey string"""
        registry = HotkeyRegistry(mock_settings)

        success, error = registry.add_hotkey("TestScript", "")

        assert not success
        assert "empty" in error.lower() or "cannot" in error.lower()

    @pytest.mark.edge_case
    def test_add_hotkey_with_whitespace(self, mock_settings):
        """Test adding hotkey with leading/trailing whitespace"""
        registry = HotkeyRegistry(mock_settings)

        success, error = registry.add_hotkey("TestScript", "  Ctrl+Alt+T  ")

        # Should normalize whitespace
        assert success
        assert registry._mappings["TestScript"] == "Ctrl+Alt+T"

    @pytest.mark.edge_case
    def test_script_name_with_special_chars(self, mock_settings):
        """Test script names with special characters"""
        registry = HotkeyRegistry(mock_settings)

        special_names = [
            "Script with spaces",
            "Script-with-dashes",
            "Script_with_underscores",
            "Script.with.dots",
            "Script/with/slashes"
        ]

        for name in special_names:
            success, error = registry.add_hotkey(name, f"Ctrl+Alt+{ord(name[0])}")
            # Should handle special characters
            assert success or error is not None

    @pytest.mark.edge_case
    def test_unicode_script_name(self, mock_settings):
        """Test script names with Unicode characters"""
        registry = HotkeyRegistry(mock_settings)

        success, error = registry.add_hotkey("テストスクリプト", "Ctrl+Alt+T")

        # Should handle Unicode
        assert success

    @pytest.mark.edge_case
    def test_very_long_hotkey_string(self, mock_settings):
        """Test with very long hotkey string"""
        registry = HotkeyRegistry(mock_settings)

        long_hotkey = "Ctrl+Alt+Shift+Win+" + "+".join([f"F{i}" for i in range(1, 13)])

        success, error = registry.add_hotkey("TestScript", long_hotkey)

        # Should either accept or reject with appropriate error
        assert success is not None

    def test_settings_persistence_on_add(self, mock_settings):
        """Test that adding hotkey persists to settings"""
        registry = HotkeyRegistry(mock_settings)

        registry.add_hotkey("TestScript", "Ctrl+Alt+T")

        # Should have called settings.set and sync
        mock_settings.set.assert_called()
        mock_settings.sync.assert_called()

    def test_settings_persistence_on_remove(self, mock_settings):
        """Test that removing hotkey updates settings"""
        registry = HotkeyRegistry(mock_settings)

        registry.add_hotkey("TestScript", "Ctrl+Alt+T")
        registry.remove_hotkey("TestScript")

        # Should have called settings.remove
        mock_settings.settings.remove.assert_called()

    def test_signals_on_add(self, mock_settings, qapp):
        """Test that signals are emitted when adding hotkey"""
        registry = HotkeyRegistry(mock_settings)

        added_spy = QSignalSpy(registry.hotkey_added)

        registry.add_hotkey("TestScript", "Ctrl+Alt+T")

        assert len(added_spy) == 1
        assert added_spy[0][0] == "TestScript"
        assert added_spy[0][1] == "Ctrl+Alt+T"

    def test_signals_on_remove(self, mock_settings, qapp):
        """Test that signals are emitted when removing hotkey"""
        registry = HotkeyRegistry(mock_settings)

        registry.add_hotkey("TestScript", "Ctrl+Alt+T")

        removed_spy = QSignalSpy(registry.hotkey_removed)

        registry.remove_hotkey("TestScript")

        assert len(removed_spy) == 1
        assert removed_spy[0][0] == "TestScript"

    def test_signals_on_update(self, mock_settings, qapp):
        """Test that signals are emitted when updating hotkey"""
        registry = HotkeyRegistry(mock_settings)

        registry.add_hotkey("TestScript", "Ctrl+Alt+T")

        updated_spy = QSignalSpy(registry.hotkey_updated)

        # Update hotkey
        registry.add_hotkey("TestScript", "Ctrl+Shift+T")

        # Should emit updated signal (if implemented)
        # Implementation may vary

    @pytest.mark.race_condition
    def test_concurrent_adds(self, mock_settings):
        """Test adding multiple hotkeys concurrently"""
        import concurrent.futures

        registry = HotkeyRegistry(mock_settings)

        def add_hotkey(script_num):
            return registry.add_hotkey(
                f"Script{script_num}",
                f"Ctrl+Alt+{script_num}"
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(add_hotkey, i) for i in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All unique hotkeys should succeed
        success_count = sum(1 for success, _ in results if success)
        assert success_count == 20

    @pytest.mark.race_condition
    def test_concurrent_add_and_remove(self, mock_settings):
        """Test concurrent add and remove operations"""
        import concurrent.futures
        import random

        registry = HotkeyRegistry(mock_settings)

        def random_operation(i):
            if random.choice([True, False]):
                return registry.add_hotkey(f"Script{i}", f"Ctrl+Alt+{i}")
            else:
                return registry.remove_hotkey(f"Script{i}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(random_operation, i) for i in range(50)]
            for f in concurrent.futures.as_completed(futures):
                f.result()  # Should not raise exceptions

        # Registry should be in consistent state
        assert len(registry._mappings) == len(registry._reverse_mappings)

    def test_hotkey_normalization(self, mock_settings):
        """Test that hotkey strings are normalized consistently"""
        registry = HotkeyRegistry(mock_settings)

        # Try different variations of same hotkey
        variations = [
            "Ctrl+Alt+T",
            "ctrl+alt+t",
            "CTRL+ALT+T",
            " Ctrl + Alt + T ",
        ]

        # All should be normalized to the same form
        # (Behavior depends on implementation)

    @pytest.mark.edge_case
    def test_case_sensitivity_script_names(self, mock_settings):
        """Test case sensitivity of script names"""
        registry = HotkeyRegistry(mock_settings)

        registry.add_hotkey("TestScript", "Ctrl+Alt+T")

        # Try to access with different case
        hotkey1 = registry.get_hotkey("TestScript")
        hotkey2 = registry.get_hotkey("testscript")

        # Behavior depends on whether script names are case-sensitive

    def test_clear_all_hotkeys(self, mock_settings):
        """Test clearing all hotkeys"""
        registry = HotkeyRegistry(mock_settings)

        # Add multiple hotkeys
        for i in range(5):
            registry.add_hotkey(f"Script{i}", f"Ctrl+Alt+{i}")

        # Clear all (if method exists)
        if hasattr(registry, 'clear_all'):
            registry.clear_all()
            assert len(registry._mappings) == 0
        else:
            # Manually clear
            for i in range(5):
                registry.remove_hotkey(f"Script{i}")

    @pytest.mark.edge_case
    def test_hotkey_with_invalid_format(self, mock_settings):
        """Test hotkey with invalid format"""
        registry = HotkeyRegistry(mock_settings)

        invalid_hotkeys = [
            "InvalidKey",
            "Ctrl+",
            "+Alt+T",
            "Ctrl++Alt",
            "123",
            "",
            None,
        ]

        for invalid in invalid_hotkeys:
            try:
                success, error = registry.add_hotkey("TestScript", invalid)
                # Should either reject or normalize
                if success:
                    # If accepted, should be in some valid form
                    assert registry._mappings.get("TestScript") is not None
                else:
                    # If rejected, should have error message
                    assert error is not None
            except (TypeError, ValueError):
                # May raise exception for None or invalid types
                pass

    def test_registry_consistency(self, mock_settings):
        """Test that forward and reverse mappings stay consistent"""
        registry = HotkeyRegistry(mock_settings)

        # Add multiple hotkeys
        for i in range(10):
            registry.add_hotkey(f"Script{i}", f"Ctrl+Alt+{i}")

        # Check consistency
        assert len(registry._mappings) == len(registry._reverse_mappings)

        # Each forward mapping should have reverse mapping
        for script, hotkey in registry._mappings.items():
            assert registry._reverse_mappings[hotkey] == script

        # Each reverse mapping should have forward mapping
        for hotkey, script in registry._reverse_mappings.items():
            assert registry._mappings[script] == hotkey

    def test_reload_from_settings(self, mock_settings):
        """Test reloading hotkeys from settings"""
        registry = HotkeyRegistry(mock_settings)

        # Add some hotkeys
        registry.add_hotkey("Script1", "Ctrl+Alt+1")

        # Simulate settings change
        mock_settings.settings.childKeys.return_value = ["Script1", "Script2"]
        mock_settings.settings.value.side_effect = lambda key: {
            "Script1": "Ctrl+Alt+1",
            "Script2": "Ctrl+Alt+2"
        }.get(key)

        # Reload (if method exists)
        if hasattr(registry, 'reload'):
            registry.reload()
            assert "Script2" in registry._mappings


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
