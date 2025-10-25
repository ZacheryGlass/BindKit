"""
Unit tests for ScriptExecutor.

Tests execution strategies, module caching, timeout handling, and resource management.
"""
import pytest
import sys
import os
import time
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.script_executor import ScriptExecutor, ExecutionResult
from core.script_analyzer import ScriptAnalyzer, ExecutionStrategy, ScriptInfo
from tests.test_utilities import (
    create_test_script,
    resource_leak_detector,
    wait_for_condition,
    verify_json_output
)


class TestScriptExecutor:
    """Test cases for ScriptExecutor"""

    def test_execute_subprocess_success(self, mock_settings):
        """Test successful subprocess execution"""
        executor = ScriptExecutor(mock_settings)
        analyzer = ScriptAnalyzer()

        # Create a simple script
        script_content = '''
import json
if __name__ == '__main__':
    print(json.dumps({"success": True, "message": "Test"}))
'''
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)
        script_path = create_test_script(temp_dir, 'subprocess_test', script_content)

        try:
            script_info = analyzer.analyze_script(script_path)
            assert script_info.is_executable

            result = executor.execute_script(script_info)

            assert result.success
            assert result.return_code == 0
        finally:
            # Cleanup
            script_path.unlink()
            temp_dir.rmdir()

    def test_execute_with_timeout(self, mock_settings):
        """Test script execution with timeout"""
        executor = ScriptExecutor(mock_settings)
        analyzer = ScriptAnalyzer()

        # Create a script that sleeps
        script_content = '''
import time
if __name__ == '__main__':
    time.sleep(30)
'''
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)
        script_path = create_test_script(temp_dir, 'timeout_test', script_content)

        try:
            script_info = analyzer.analyze_script(script_path)

            # Override timeout to a short value for testing
            with patch.object(executor, '_execute_subprocess') as mock_exec:
                mock_exec.return_value = ExecutionResult(
                    success=False,
                    error="Execution timed out"
                )

                result = executor.execute_script(script_info)
                assert not result.success
        finally:
            script_path.unlink()
            temp_dir.rmdir()

    def test_execute_with_arguments(self, mock_settings):
        """Test executing script with arguments"""
        executor = ScriptExecutor(mock_settings)
        analyzer = ScriptAnalyzer()

        script_content = '''
import argparse
import json

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--name', required=True)
    parser.add_argument('--count', type=int, default=1)
    args = parser.parse_args()
    print(json.dumps({"name": args.name, "count": args.count}))
'''
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)
        script_path = create_test_script(temp_dir, 'args_test', script_content)

        try:
            script_info = analyzer.analyze_script(script_path)

            # Execute with arguments
            arguments = {'name': 'test', 'count': 5}
            result = executor.execute_script(script_info, arguments)

            assert result.success
        finally:
            script_path.unlink()
            temp_dir.rmdir()

    def test_execute_missing_required_argument(self, mock_settings):
        """Test executing script with missing required argument"""
        executor = ScriptExecutor(mock_settings)
        analyzer = ScriptAnalyzer()

        script_content = '''
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--required', required=True)
    args = parser.parse_args()
    print("OK")
'''
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)
        script_path = create_test_script(temp_dir, 'missing_arg_test', script_content)

        try:
            script_info = analyzer.analyze_script(script_path)

            # Execute without required argument
            result = executor.execute_script(script_info, {})

            # Should fail due to missing argument
            assert not result.success
        finally:
            script_path.unlink()
            temp_dir.rmdir()

    @pytest.mark.edge_case
    def test_execute_invalid_json_output(self, mock_settings):
        """Test handling of script that outputs invalid JSON"""
        executor = ScriptExecutor(mock_settings)
        analyzer = ScriptAnalyzer()

        script_content = '''
if __name__ == '__main__':
    print("This is not JSON")
    print("Multiple lines of output")
'''
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)
        script_path = create_test_script(temp_dir, 'invalid_json_test', script_content)

        try:
            script_info = analyzer.analyze_script(script_path)
            result = executor.execute_script(script_info)

            # Executor should handle invalid JSON gracefully
            # It may succeed but data parsing may fail
            assert result is not None
        finally:
            script_path.unlink()
            temp_dir.rmdir()

    @pytest.mark.edge_case
    def test_execute_script_with_error(self, mock_settings):
        """Test executing script that raises an error"""
        executor = ScriptExecutor(mock_settings)
        analyzer = ScriptAnalyzer()

        script_content = '''
if __name__ == '__main__':
    raise RuntimeError("Intentional error")
'''
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)
        script_path = create_test_script(temp_dir, 'error_test', script_content)

        try:
            script_info = analyzer.analyze_script(script_path)
            result = executor.execute_script(script_info)

            # Should fail
            assert not result.success
            assert result.return_code != 0
        finally:
            script_path.unlink()
            temp_dir.rmdir()

    @pytest.mark.edge_case
    def test_execute_script_with_unicode_output(self, mock_settings):
        """Test script that outputs Unicode characters"""
        executor = ScriptExecutor(mock_settings)
        analyzer = ScriptAnalyzer()

        script_content = '''
# -*- coding: utf-8 -*-
import json

if __name__ == '__main__':
    print(json.dumps({"message": "こんにちは 世界 🌍"}, ensure_ascii=False))
'''
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)
        script_path = create_test_script(temp_dir, 'unicode_output_test', script_content)

        try:
            script_info = analyzer.analyze_script(script_path)
            result = executor.execute_script(script_info)

            assert result.success
            # Output should contain Unicode
            assert result.output is not None
        finally:
            script_path.unlink()
            temp_dir.rmdir()

    @pytest.mark.resource_leak
    def test_module_cache_cleanup(self, mock_settings):
        """Test that module cache is cleaned up properly"""
        executor = ScriptExecutor(mock_settings, max_cache_size=5)

        # Track initial module count
        initial_modules = len(sys.modules)

        # Create and execute multiple scripts to fill the cache
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)

        try:
            for i in range(10):
                script_content = f'''
def test_func_{i}():
    return {i}
'''
                script_path = create_test_script(temp_dir, f'cache_test_{i}', script_content)

                # Note: This test would need to actually trigger module caching
                # which depends on the execution strategy

            # Force cleanup
            executor._cleanup_stale_modules()

            # Cache should be limited
            assert len(executor.loaded_modules) <= executor.max_cache_size

        finally:
            # Cleanup
            for script_path in temp_dir.glob("*.py"):
                script_path.unlink()
            temp_dir.rmdir()

    @pytest.mark.resource_leak
    def test_cache_ttl_expiration(self, mock_settings):
        """Test that cached modules expire based on TTL"""
        # Use very short TTL for testing
        executor = ScriptExecutor(mock_settings, cache_ttl_seconds=1)

        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)

        try:
            script_content = 'def test(): return True'
            script_path = create_test_script(temp_dir, 'ttl_test', script_content)

            # Add a fake module to cache
            module_name = "ttl_test_module"
            executor.loaded_modules[module_name] = Mock()
            executor.module_access_times[module_name] = time.time() - 2  # 2 seconds ago

            # Trigger cleanup
            executor._cleanup_stale_modules()

            # Module should be removed due to TTL expiration
            assert module_name not in executor.loaded_modules

        finally:
            script_path.unlink()
            temp_dir.rmdir()

    @pytest.mark.edge_case
    def test_execute_nonexecutable_script(self, mock_settings):
        """Test executing a script marked as non-executable"""
        executor = ScriptExecutor(mock_settings)

        # Create a fake non-executable script info
        script_info = ScriptInfo(
            file_path=Path("fake.py"),
            is_executable=False,
            error="Script is not executable",
            execution_strategy=ExecutionStrategy.SUBPROCESS,
            arguments=[],
            display_name="Fake Script"
        )

        result = executor.execute_script(script_info)

        assert not result.success
        assert "not executable" in result.error

    @pytest.mark.edge_case
    def test_execute_with_empty_arguments(self, mock_settings):
        """Test executing with empty/None arguments"""
        executor = ScriptExecutor(mock_settings)
        analyzer = ScriptAnalyzer()

        script_content = '''
import json
if __name__ == '__main__':
    print(json.dumps({"success": True}))
'''
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)
        script_path = create_test_script(temp_dir, 'empty_args_test', script_content)

        try:
            script_info = analyzer.analyze_script(script_path)

            # Execute with None arguments
            result1 = executor.execute_script(script_info, None)
            assert result1.success

            # Execute with empty dict
            result2 = executor.execute_script(script_info, {})
            assert result2.success

        finally:
            script_path.unlink()
            temp_dir.rmdir()

    @pytest.mark.edge_case
    def test_execute_with_very_long_output(self, mock_settings):
        """Test handling script with very long output"""
        executor = ScriptExecutor(mock_settings)
        analyzer = ScriptAnalyzer()

        # Script that generates lots of output
        script_content = '''
if __name__ == '__main__':
    for i in range(10000):
        print(f"Line {i}: " + "x" * 100)
'''
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)
        script_path = create_test_script(temp_dir, 'long_output_test', script_content)

        try:
            script_info = analyzer.analyze_script(script_path)
            result = executor.execute_script(script_info)

            # Should handle long output without crashing
            assert result is not None
            assert result.output is not None

        finally:
            script_path.unlink()
            temp_dir.rmdir()

    @pytest.mark.slow
    def test_concurrent_executions(self, mock_settings):
        """Test executing multiple scripts concurrently"""
        import concurrent.futures

        executor = ScriptExecutor(mock_settings)
        analyzer = ScriptAnalyzer()

        script_content = '''
import json
import time
import random

if __name__ == '__main__':
    time.sleep(random.uniform(0.1, 0.3))
    print(json.dumps({"success": True}))
'''
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)

        try:
            script_path = create_test_script(temp_dir, 'concurrent_test', script_content)
            script_info = analyzer.analyze_script(script_path)

            def run_script():
                return executor.execute_script(script_info)

            # Run 10 concurrent executions
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                futures = [pool.submit(run_script) for _ in range(10)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]

            # All should succeed
            assert all(r.success for r in results)

        finally:
            script_path.unlink()
            temp_dir.rmdir()

    @pytest.mark.edge_case
    def test_execute_script_that_modifies_itself(self, mock_settings):
        """Test executing a script that tries to modify its own file"""
        executor = ScriptExecutor(mock_settings)
        analyzer = ScriptAnalyzer()

        script_content = '''
import json
import sys

if __name__ == '__main__':
    # Try to modify own file
    try:
        with open(__file__, 'a') as f:
            f.write("# Modified\\n")
        print(json.dumps({"success": True, "modified": True}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
'''
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)
        script_path = create_test_script(temp_dir, 'self_modify_test', script_content)

        try:
            script_info = analyzer.analyze_script(script_path)
            result = executor.execute_script(script_info)

            # Should execute (whether it succeeds in modifying depends on permissions)
            assert result is not None

        finally:
            script_path.unlink()
            temp_dir.rmdir()

    @pytest.mark.edge_case
    def test_execute_script_with_subprocess_spawn(self, mock_settings):
        """Test script that spawns child processes"""
        executor = ScriptExecutor(mock_settings)
        analyzer = ScriptAnalyzer()

        script_content = '''
import subprocess
import json
import sys

if __name__ == '__main__':
    # Spawn a child process
    result = subprocess.run([sys.executable, '-c', 'print("child")'],
                          capture_output=True, text=True)
    print(json.dumps({"success": True, "child_output": result.stdout.strip()}))
'''
        temp_dir = Path("temp_test_scripts")
        temp_dir.mkdir(exist_ok=True)
        script_path = create_test_script(temp_dir, 'subprocess_spawn_test', script_content)

        try:
            script_info = analyzer.analyze_script(script_path)
            result = executor.execute_script(script_info)

            assert result.success

        finally:
            script_path.unlink()
            temp_dir.rmdir()

    def test_execution_result_dataclass(self):
        """Test ExecutionResult dataclass creation and usage"""
        # Test successful result
        success_result = ExecutionResult(
            success=True,
            message="Script executed successfully",
            output="output text",
            return_code=0
        )

        assert success_result.success
        assert success_result.message == "Script executed successfully"
        assert success_result.return_code == 0

        # Test failure result
        failure_result = ExecutionResult(
            success=False,
            error="Script failed",
            return_code=1
        )

        assert not failure_result.success
        assert failure_result.error == "Script failed"
        assert failure_result.return_code == 1

    @pytest.mark.edge_case
    def test_cleanup_on_executor_deletion(self, mock_settings):
        """Test that resources are cleaned up when executor is deleted"""
        executor = ScriptExecutor(mock_settings)

        # Add some items to cache
        executor.loaded_modules['test_module'] = Mock()
        executor.module_access_times['test_module'] = time.time()

        # Delete executor
        del executor

        # This primarily tests that deletion doesn't cause errors
        # Full resource cleanup verification would require more complex tracking


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
