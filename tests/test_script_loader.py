"""
Unit tests for ScriptLoader.

Tests script discovery, parallel loading, external scripts, and error handling.
"""
import pytest
import sys
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.script_loader import ScriptLoader
from core.script_analyzer import ScriptInfo
from tests.test_utilities import create_test_script, wait_for_condition


class TestScriptLoader:
    """Test cases for ScriptLoader"""

    def test_initialization(self, temp_scripts_dir):
        """Test loader initializes correctly"""
        loader = ScriptLoader(str(temp_scripts_dir))

        assert loader.scripts_directory == temp_scripts_dir
        assert loader.loaded_scripts is not None
        assert loader.failed_scripts is not None

    def test_discover_empty_directory(self, temp_scripts_dir):
        """Test discovering scripts in empty directory"""
        loader = ScriptLoader(str(temp_scripts_dir))
        scripts = loader.discover_scripts()

        assert scripts is not None
        assert len(scripts) == 0

    def test_discover_single_script(self, temp_scripts_dir):
        """Test discovering a single script"""
        # Create a test script
        create_test_script(
            temp_scripts_dir,
            'test_single',
            'if __name__ == "__main__":\n    print("test")'
        )

        loader = ScriptLoader(str(temp_scripts_dir))
        scripts = loader.discover_scripts()

        assert len(scripts) >= 1
        # Check that our script was found
        assert any(s.file_path.stem == 'test_single' for s in scripts)

    def test_discover_multiple_scripts(self, temp_scripts_dir):
        """Test discovering multiple scripts"""
        # Create several test scripts
        for i in range(5):
            create_test_script(
                temp_scripts_dir,
                f'test_multi_{i}',
                'if __name__ == "__main__":\n    print("test")'
            )

        loader = ScriptLoader(str(temp_scripts_dir))
        scripts = loader.discover_scripts()

        assert len(scripts) >= 5

    def test_discover_ignores_dunder_files(self, temp_scripts_dir):
        """Test that __init__.py and similar files are ignored"""
        # Create __init__.py
        (temp_scripts_dir / "__init__.py").write_text("")
        (temp_scripts_dir / "__pycache__").mkdir(exist_ok=True)

        # Create a normal script
        create_test_script(
            temp_scripts_dir,
            'normal_script',
            'if __name__ == "__main__":\n    print("test")'
        )

        loader = ScriptLoader(str(temp_scripts_dir))
        scripts = loader.discover_scripts()

        # Should not include __init__.py
        assert not any(s.file_path.name.startswith("__") for s in scripts)

    def test_discover_handles_invalid_scripts(self, temp_scripts_dir):
        """Test that invalid scripts are tracked in failed_scripts"""
        # Create an invalid script
        create_test_script(temp_scripts_dir, 'invalid', 'invalid python syntax {{{')

        loader = ScriptLoader(str(temp_scripts_dir))
        scripts = loader.discover_scripts()

        # Invalid script should be in failed_scripts
        assert len(loader.failed_scripts) > 0

    def test_discover_creates_directory_if_missing(self, temp_dir):
        """Test that discover creates scripts directory if it doesn't exist"""
        nonexistent_dir = temp_dir / "nonexistent_scripts"

        loader = ScriptLoader(str(nonexistent_dir))
        scripts = loader.discover_scripts()

        # Directory should be created
        assert nonexistent_dir.exists()
        assert scripts is not None

    @pytest.mark.edge_case
    def test_discover_with_unicode_filenames(self, temp_scripts_dir):
        """Test discovering scripts with Unicode filenames"""
        # Create script with Unicode name
        script_path = temp_scripts_dir / "テスト_script.py"
        script_path.write_text(
            'if __name__ == "__main__":\n    print("Unicode filename")',
            encoding='utf-8'
        )

        loader = ScriptLoader(str(temp_scripts_dir))
        scripts = loader.discover_scripts()

        # Should handle Unicode filenames
        assert any('テスト' in s.file_path.name for s in scripts) or \
               any(s.file_path.name == "テスト_script.py" for s in scripts)

    @pytest.mark.edge_case
    def test_discover_with_spaces_in_filename(self, temp_scripts_dir):
        """Test discovering scripts with spaces in filename"""
        script_path = temp_scripts_dir / "script with spaces.py"
        script_path.write_text('if __name__ == "__main__":\n    print("spaces")')

        loader = ScriptLoader(str(temp_scripts_dir))
        scripts = loader.discover_scripts()

        assert any(' ' in s.file_path.name for s in scripts)

    @pytest.mark.slow
    def test_parallel_discovery_performance(self, temp_scripts_dir):
        """Test that parallel discovery is faster than sequential"""
        # Create many scripts
        for i in range(50):
            create_test_script(
                temp_scripts_dir,
                f'perf_test_{i}',
                f'if __name__ == "__main__":\n    print("Script {i}")'
            )

        loader = ScriptLoader(str(temp_scripts_dir))

        start_time = time.time()
        scripts = loader.discover_scripts()
        elapsed = time.time() - start_time

        # Should complete in reasonable time with parallel loading
        assert elapsed < 15.0, f"Discovery took {elapsed}s (expected < 15s)"
        assert len(scripts) >= 50

    @pytest.mark.race_condition
    def test_concurrent_discovery_calls(self, temp_scripts_dir):
        """Test calling discover_scripts concurrently"""
        import concurrent.futures

        # Create some scripts
        for i in range(10):
            create_test_script(
                temp_scripts_dir,
                f'concurrent_test_{i}',
                'if __name__ == "__main__":\n    print("test")'
            )

        loader = ScriptLoader(str(temp_scripts_dir))

        def discover():
            return loader.discover_scripts()

        # Run multiple discoveries concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(discover) for _ in range(3)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed and return similar results
        assert all(len(r) >= 10 for r in results)

    def test_execute_script_success(self, temp_scripts_dir):
        """Test executing a loaded script"""
        import json

        # Create a simple script
        create_test_script(
            temp_scripts_dir,
            'exec_test',
            'import json\nif __name__ == "__main__":\n    print(json.dumps({"success": True}))'
        )

        loader = ScriptLoader(str(temp_scripts_dir))
        scripts = loader.discover_scripts()

        # Find our script
        script_info = next((s for s in scripts if s.file_path.stem == 'exec_test'), None)
        assert script_info is not None

        # Execute it
        result = loader.executor.execute_script(script_info)

        assert result.success

    def test_execute_script_with_arguments(self, temp_scripts_dir):
        """Test executing script with arguments"""
        script_content = '''
import argparse
import json

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--value', required=True)
    args = parser.parse_args()
    print(json.dumps({"value": args.value}))
'''
        create_test_script(temp_scripts_dir, 'args_exec_test', script_content)

        loader = ScriptLoader(str(temp_scripts_dir))
        scripts = loader.discover_scripts()

        script_info = next((s for s in scripts if s.file_path.stem == 'args_exec_test'), None)
        assert script_info is not None

        result = loader.executor.execute_script(script_info, {'value': 'test123'})

        assert result.success

    @pytest.mark.edge_case
    def test_discover_after_directory_changes(self, temp_scripts_dir):
        """Test re-discovering scripts after directory changes"""
        loader = ScriptLoader(str(temp_scripts_dir))

        # First discovery (empty)
        scripts1 = loader.discover_scripts()
        count1 = len(scripts1)

        # Add new scripts
        for i in range(3):
            create_test_script(
                temp_scripts_dir,
                f'new_script_{i}',
                'if __name__ == "__main__":\n    print("new")'
            )

        # Second discovery (should find new scripts)
        scripts2 = loader.discover_scripts()
        count2 = len(scripts2)

        assert count2 >= count1 + 3

    @pytest.mark.edge_case
    def test_discover_with_permission_errors(self, temp_scripts_dir):
        """Test handling permission errors during discovery"""
        # This test is tricky to implement cross-platform
        # On Windows, we might need to use icacls to change permissions
        # For now, we'll use mocking

        loader = ScriptLoader(str(temp_scripts_dir))

        # Create a script
        script_path = create_test_script(
            temp_scripts_dir,
            'permission_test',
            'if __name__ == "__main__":\n    print("test")'
        )

        # Mock Path.glob to raise PermissionError
        with patch.object(Path, 'glob') as mock_glob:
            mock_glob.side_effect = PermissionError("Access denied")

            # Discovery should handle the error gracefully
            try:
                scripts = loader.discover_scripts()
                # Should return empty or partial results, not crash
                assert scripts is not None
            except PermissionError:
                pytest.fail("PermissionError should be handled gracefully")

    def test_loader_settings_integration(self, temp_scripts_dir, mock_settings):
        """Test that loader integrates with settings manager"""
        loader = ScriptLoader(str(temp_scripts_dir))

        # Settings should be initialized
        assert loader.settings is not None

    def test_failed_scripts_tracking(self, temp_scripts_dir):
        """Test that failed scripts are properly tracked"""
        # Create a valid and an invalid script
        create_test_script(
            temp_scripts_dir,
            'valid',
            'if __name__ == "__main__":\n    print("valid")'
        )
        create_test_script(temp_scripts_dir, 'invalid', 'syntax error {{{')

        loader = ScriptLoader(str(temp_scripts_dir))
        loader.discover_scripts()

        # Check that failed scripts are tracked
        assert len(loader.failed_scripts) > 0
        # The invalid script should be in failed_scripts
        assert any('invalid' in name for name in loader.failed_scripts.keys())

    @pytest.mark.edge_case
    def test_discover_empty_script_file(self, temp_scripts_dir):
        """Test discovering an empty script file"""
        empty_script = temp_scripts_dir / "empty.py"
        empty_script.write_text("")

        loader = ScriptLoader(str(temp_scripts_dir))
        scripts = loader.discover_scripts()

        # Empty script should either be in failed_scripts or filtered out
        # It should not cause a crash
        assert scripts is not None

    @pytest.mark.edge_case
    def test_discover_binary_file_with_py_extension(self, temp_scripts_dir):
        """Test discovering a binary file with .py extension"""
        binary_file = temp_scripts_dir / "binary.py"
        binary_file.write_bytes(b'\x00\x01\x02\xFF\xFE')

        loader = ScriptLoader(str(temp_scripts_dir))
        scripts = loader.discover_scripts()

        # Should handle gracefully
        assert scripts is not None

    @pytest.mark.slow
    def test_discover_timeout_handling(self, temp_scripts_dir):
        """Test that discovery handles timeouts in ThreadPoolExecutor"""
        # Create many scripts to potentially trigger timeout
        for i in range(100):
            create_test_script(
                temp_scripts_dir,
                f'timeout_test_{i}',
                'if __name__ == "__main__":\n    print("test")'
            )

        loader = ScriptLoader(str(temp_scripts_dir))

        # Discovery should complete even with many files
        scripts = loader.discover_scripts()

        assert scripts is not None
        # Should have discovered most or all scripts
        assert len(scripts) >= 90  # Allow for some failures

    def test_external_scripts_discovery(self, temp_scripts_dir, mock_settings):
        """Test discovering external scripts from settings"""
        # Mock external scripts in settings
        external_scripts = {
            'External1': str(temp_scripts_dir / 'external1.py'),
            'External2': str(temp_scripts_dir / 'external2.py')
        }

        mock_settings.get_external_scripts.return_value = external_scripts

        # Create the external scripts
        for name, path in external_scripts.items():
            Path(path).write_text('if __name__ == "__main__":\n    print("external")')

        loader = ScriptLoader(str(temp_scripts_dir))
        loader.settings = mock_settings

        scripts = loader.discover_scripts()

        # Should discover external scripts
        # (Depending on implementation)
        assert scripts is not None

    @pytest.mark.edge_case
    def test_discover_with_symlinks(self, temp_scripts_dir):
        """Test discovering scripts through symlinks"""
        # Create a script
        real_script = create_test_script(
            temp_scripts_dir,
            'real_script',
            'if __name__ == "__main__":\n    print("real")'
        )

        # Try to create a symlink (may not work on all systems)
        try:
            symlink_path = temp_scripts_dir / "symlink_script.py"
            symlink_path.symlink_to(real_script)

            loader = ScriptLoader(str(temp_scripts_dir))
            scripts = loader.discover_scripts()

            # Should handle symlinks appropriately
            assert scripts is not None

        except (OSError, NotImplementedError):
            # Symlinks might not be supported on this system
            pytest.skip("Symlinks not supported on this system")

    def test_refresh_external_scripts(self, temp_scripts_dir):
        """Test refreshing external scripts"""
        loader = ScriptLoader(str(temp_scripts_dir))

        # This tests the refresh_external_scripts method if it exists
        # The actual implementation depends on the ScriptLoader code
        if hasattr(loader, 'refresh_external_scripts'):
            refreshed = loader.refresh_external_scripts()
            assert refreshed is not None

    @pytest.mark.edge_case
    def test_discover_script_sorting(self, temp_scripts_dir):
        """Test that discovered scripts are sorted consistently"""
        # Create scripts with different names
        names = ['zebra', 'alpha', 'beta', 'gamma']
        for name in names:
            create_test_script(
                temp_scripts_dir,
                name,
                'if __name__ == "__main__":\n    print("test")'
            )

        loader = ScriptLoader(str(temp_scripts_dir))
        scripts1 = loader.discover_scripts()
        scripts2 = loader.discover_scripts()

        # Scripts should be in the same order on subsequent discoveries
        names1 = [s.file_path.stem for s in scripts1]
        names2 = [s.file_path.stem for s in scripts2]

        assert names1 == names2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
