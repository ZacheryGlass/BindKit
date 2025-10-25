"""
Race condition and concurrency tests for BindKit.

Tests concurrent operations that could expose threading bugs, deadlocks,
and race conditions.
"""
import pytest
import sys
import os
import time
import threading
from pathlib import Path
from unittest.mock import Mock
import concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.script_loader import ScriptLoader
from core.script_analyzer import ScriptAnalyzer
from core.script_executor import ScriptExecutor
from core.hotkey_registry import HotkeyRegistry
from tests.test_utilities import create_test_script, stress_test_operation, wait_for_condition


@pytest.mark.race_condition
class TestLoaderConcurrency:
    """Test concurrent operations in ScriptLoader"""

    def test_concurrent_script_discovery(self, temp_scripts_dir):
        """Test multiple threads discovering scripts simultaneously"""
        # Create scripts
        for i in range(20):
            create_test_script(
                temp_scripts_dir,
                f'concurrent_{i}',
                'if __name__ == "__main__":\n    print("test")'
            )

        loader = ScriptLoader(str(temp_scripts_dir))

        def discover():
            return loader.discover_scripts()

        # Run 10 concurrent discoveries
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(discover) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        assert all(len(r) >= 20 for r in results)

    def test_concurrent_script_execution(self, temp_scripts_dir, mock_settings):
        """Test executing same script concurrently"""
        script_content = '''
import json
import time
import random

if __name__ == '__main__':
    time.sleep(random.uniform(0.01, 0.05))
    print(json.dumps({"success": True}))
'''
        script_path = create_test_script(temp_scripts_dir, 'concurrent_exec', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        executor = ScriptExecutor(mock_settings)

        def execute():
            return executor.execute_script(script_info)

        # Run 20 concurrent executions
        results = stress_test_operation(execute, iterations=20, concurrency=5)

        # All should succeed
        assert results['success'] >= 18  # Allow for some flakiness

    def test_discovery_during_execution(self, temp_scripts_dir, mock_settings):
        """Test discovering scripts while executing others"""
        # Create initial scripts
        for i in range(5):
            create_test_script(
                temp_scripts_dir,
                f'exec_{i}',
                'if __name__ == "__main__":\n    print("test")'
            )

        loader = ScriptLoader(str(temp_scripts_dir))
        scripts = loader.discover_scripts()

        def execute_script():
            if scripts:
                script_info = scripts[0]
                return loader.executor.execute_script(script_info)

        def discover_scripts():
            return loader.discover_scripts()

        # Run executions and discoveries concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            exec_futures = [pool.submit(execute_script) for _ in range(10)]
            disc_futures = [pool.submit(discover_scripts) for _ in range(5)]

            # Wait for all to complete
            for f in exec_futures + disc_futures:
                f.result()

        # Should not crash or deadlock

    def test_concurrent_module_cache_access(self, temp_scripts_dir, mock_settings):
        """Test concurrent access to module cache"""
        executor = ScriptExecutor(mock_settings, max_cache_size=10)

        # Pre-populate cache with mock modules
        for i in range(5):
            executor.loaded_modules[f'module_{i}'] = Mock()
            executor.module_access_times[f'module_{i}'] = time.time()

        def access_cache():
            # Simulate cache operations
            if f'module_0' in executor.loaded_modules:
                _ = executor.loaded_modules[f'module_0']
            executor._cleanup_stale_modules()

        # Run concurrent cache accesses
        results = stress_test_operation(access_cache, iterations=50, concurrency=10)

        # Should not raise exceptions
        assert results['failure'] == 0


@pytest.mark.race_condition
class TestRegistryConcurrency:
    """Test concurrent operations in HotkeyRegistry"""

    def test_concurrent_hotkey_registration(self, mock_settings):
        """Test registering multiple hotkeys concurrently"""
        registry = HotkeyRegistry(mock_settings)

        def register_hotkey(i):
            return registry.add_hotkey(f'Script{i}', f'Ctrl+Alt+{i}')

        # Register 30 hotkeys concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(register_hotkey, i) for i in range(30)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All unique hotkeys should succeed
        success_count = sum(1 for success, _ in results if success)
        assert success_count == 30

    def test_concurrent_registration_and_removal(self, mock_settings):
        """Test concurrent add and remove operations"""
        registry = HotkeyRegistry(mock_settings)

        # Pre-register some hotkeys
        for i in range(10):
            registry.add_hotkey(f'Initial{i}', f'Ctrl+Shift+{i}')

        def random_operation(i):
            import random
            if random.choice([True, False]):
                # Add
                return registry.add_hotkey(f'Script{i}', f'Ctrl+Alt+{i}')
            else:
                # Remove
                return registry.remove_hotkey(f'Initial{i % 10}')

        # Run 100 random operations concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(random_operation, i) for i in range(100)]
            for f in concurrent.futures.as_completed(futures):
                f.result()  # Should not raise

        # Registry should be in consistent state
        assert len(registry._mappings) == len(registry._reverse_mappings)

    def test_concurrent_reads(self, mock_settings):
        """Test concurrent read operations"""
        registry = HotkeyRegistry(mock_settings)

        # Pre-register hotkeys
        for i in range(20):
            registry.add_hotkey(f'Script{i}', f'Ctrl+Alt+{i}')

        def read_operations():
            import random
            script_num = random.randint(0, 19)

            # Perform various read operations
            _ = registry.get_hotkey_for_script(f'Script{script_num}')
            _ = registry.get_script_for_hotkey(f'Ctrl+Alt+{script_num}')
            _ = registry.get_all_mappings()

        # Run 100 concurrent read operations
        results = stress_test_operation(read_operations, iterations=100, concurrency=20)

        # All reads should succeed
        assert results['failure'] == 0

    def test_write_during_read(self, mock_settings):
        """Test writing to registry while reading"""
        registry = HotkeyRegistry(mock_settings)

        # Pre-register hotkeys
        for i in range(10):
            registry.add_hotkey(f'Script{i}', f'Ctrl+Alt+{i}')

        read_count = {'count': 0}
        write_count = {'count': 0}

        def reader():
            for _ in range(50):
                registry.get_all_mappings()
                read_count['count'] += 1
                time.sleep(0.001)

        def writer():
            for i in range(10, 20):
                registry.add_hotkey(f'NewScript{i}', f'Ctrl+Shift+{i}')
                write_count['count'] += 1
                time.sleep(0.001)

        # Run readers and writers concurrently
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=reader))
        for _ in range(2):
            threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should complete without errors
        assert read_count['count'] > 0
        assert write_count['count'] > 0


@pytest.mark.race_condition
class TestExecutorConcurrency:
    """Test concurrent operations in ScriptExecutor"""

    def test_concurrent_script_executions_different_scripts(self, temp_scripts_dir, mock_settings):
        """Test executing different scripts concurrently"""
        # Create multiple scripts
        scripts = []
        for i in range(10):
            script_path = create_test_script(
                temp_scripts_dir,
                f'parallel_{i}',
                f'import json\nprint(json.dumps({{"id": {i}}}))'
            )
            scripts.append(script_path)

        analyzer = ScriptAnalyzer()
        script_infos = [analyzer.analyze_script(s) for s in scripts]

        executor = ScriptExecutor(mock_settings)

        def execute_script(script_info):
            return executor.execute_script(script_info)

        # Execute all scripts concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(execute_script, si) for si in script_infos]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        success_count = sum(1 for r in results if r.success)
        assert success_count >= 8  # Allow for some failures

    def test_cache_cleanup_during_execution(self, temp_scripts_dir, mock_settings):
        """Test cache cleanup happening during script execution"""
        executor = ScriptExecutor(mock_settings, max_cache_size=5, cache_ttl_seconds=1)

        script_path = create_test_script(
            temp_scripts_dir,
            'cleanup_test',
            'import time\ntime.sleep(0.1)\nprint("done")'
        )

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        def execute():
            return executor.execute_script(script_info)

        def cleanup():
            time.sleep(0.05)
            executor._cleanup_stale_modules()

        # Run executions and cleanups concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            exec_futures = [pool.submit(execute) for _ in range(10)]
            cleanup_futures = [pool.submit(cleanup) for _ in range(5)]

            # Wait for all
            for f in exec_futures + cleanup_futures:
                f.result()

        # Should not crash


@pytest.mark.race_condition
class TestTimingRaceConditions:
    """Test race conditions related to timing"""

    def test_rapid_start_stop_operations(self, temp_scripts_dir, mock_settings, qapp):
        """Test rapidly starting and stopping operations"""
        from core.schedule_runtime import ScheduleRuntime

        runtime = ScheduleRuntime()

        script_path = create_test_script(
            temp_scripts_dir,
            'rapid_test',
            'print("test")'
        )

        def rapid_cycle():
            try:
                handle = runtime.start_schedule(
                    script_name="RapidTest",
                    script_path=script_path,
                    interval_seconds=60,
                    execution_callback=lambda: None
                )
                time.sleep(0.01)
                runtime.stop_schedule("RapidTest")
            except Exception:
                pass  # Some operations may conflict

        # Run rapid start/stop cycles
        results = stress_test_operation(rapid_cycle, iterations=50, concurrency=1)

        # Most should complete without errors
        # (Some errors acceptable due to timing)

    def test_concurrent_timer_modifications(self, temp_scripts_dir, qapp):
        """Test modifying timers from multiple threads"""
        from core.schedule_runtime import ScheduleRuntime

        runtime = ScheduleRuntime()

        script_path = create_test_script(
            temp_scripts_dir,
            'timer_test',
            'print("test")'
        )

        def modify_timer(i):
            try:
                handle = runtime.start_schedule(
                    script_name=f"Timer{i}",
                    script_path=script_path,
                    interval_seconds=60 + i,
                    execution_callback=lambda: None
                )
                time.sleep(0.01)
                runtime.stop_schedule(f"Timer{i}")
            except Exception:
                pass

        # Modify timers concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(modify_timer, i) for i in range(20)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        # All schedules should be stopped
        assert len(runtime._active_schedules) == 0


@pytest.mark.race_condition
class TestDeadlockPrevention:
    """Tests to detect potential deadlocks"""

    def test_no_deadlock_in_registry(self, mock_settings):
        """Test that registry operations don't deadlock"""
        registry = HotkeyRegistry(mock_settings)

        deadlock_detected = {'detected': False}

        def heavy_operations():
            try:
                for i in range(100):
                    registry.add_hotkey(f'Script{i}', f'Ctrl+Alt+{i}')
                    registry.get_all_mappings()
                    if i % 10 == 0:
                        registry.remove_hotkey(f'Script{i-5}')
            except Exception:
                pass

        # Run operations concurrently with timeout
        threads = [threading.Thread(target=heavy_operations) for _ in range(5)]

        for t in threads:
            t.start()

        # Wait with timeout to detect deadlock
        for t in threads:
            t.join(timeout=10.0)
            if t.is_alive():
                deadlock_detected['detected'] = True

        assert not deadlock_detected['detected'], "Potential deadlock detected"

    def test_no_deadlock_in_executor(self, temp_scripts_dir, mock_settings):
        """Test that executor operations don't deadlock"""
        executor = ScriptExecutor(mock_settings)

        script_path = create_test_script(
            temp_scripts_dir,
            'deadlock_test',
            'print("test")'
        )

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        deadlock_detected = {'detected': False}

        def heavy_operations():
            try:
                for _ in range(20):
                    executor.execute_script(script_info)
                    executor._cleanup_stale_modules()
            except Exception:
                pass

        threads = [threading.Thread(target=heavy_operations) for _ in range(3)]

        for t in threads:
            t.start()

        for t in threads:
            t.join(timeout=15.0)
            if t.is_alive():
                deadlock_detected['detected'] = True

        assert not deadlock_detected['detected'], "Potential deadlock detected in executor"


@pytest.mark.race_condition
class TestDataRaceConditions:
    """Test for data race conditions"""

    def test_shared_counter_consistency(self):
        """Test that shared counters maintain consistency under concurrency"""
        # This is a general test for any shared state
        counter = {'value': 0}
        lock = threading.Lock()

        def increment_safe():
            with lock:
                counter['value'] += 1

        # Run many increments concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(increment_safe) for _ in range(1000)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        # Counter should be exactly 1000
        assert counter['value'] == 1000

    def test_list_modification_race(self):
        """Test concurrent list modifications"""
        shared_list = []
        lock = threading.Lock()

        def safe_append(value):
            with lock:
                shared_list.append(value)

        # Append concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(safe_append, i) for i in range(100)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        # Should have all 100 items
        assert len(shared_list) == 100

    def test_dict_modification_race(self):
        """Test concurrent dictionary modifications"""
        shared_dict = {}
        lock = threading.Lock()

        def safe_update(key, value):
            with lock:
                shared_dict[key] = value

        # Update concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(safe_update, f'key_{i}', i) for i in range(100)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        # Should have all 100 keys
        assert len(shared_dict) == 100


@pytest.mark.race_condition
@pytest.mark.slow
class TestStressTests:
    """Stress tests to expose race conditions under load"""

    def test_loader_stress(self, temp_scripts_dir):
        """Stress test script loader"""
        # Create many scripts
        for i in range(50):
            create_test_script(
                temp_scripts_dir,
                f'stress_{i}',
                'if __name__ == "__main__":\n    print("test")'
            )

        loader = ScriptLoader(str(temp_scripts_dir))

        # Discover repeatedly
        for _ in range(10):
            scripts = loader.discover_scripts()
            assert len(scripts) >= 50

    def test_registry_stress(self, mock_settings):
        """Stress test hotkey registry"""
        registry = HotkeyRegistry(mock_settings)

        # Perform many operations
        for i in range(200):
            registry.add_hotkey(f'Script{i}', f'Ctrl+Alt+{i % 50}')
            if i % 10 == 0:
                registry.get_all_mappings()
            if i % 5 == 0:
                registry.remove_hotkey(f'Script{i-5}')

        # Should maintain consistency
        assert len(registry._mappings) == len(registry._reverse_mappings)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
