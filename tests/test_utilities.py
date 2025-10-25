"""
Utility functions and helpers for BindKit tests.
"""
import time
import psutil
import gc
import sys
from pathlib import Path
from typing import Callable, Any, Optional
from contextlib import contextmanager


class ResourceTracker:
    """
    Track system resources to detect leaks.
    """

    def __init__(self):
        self.initial_handles = None
        self.initial_memory = None
        self.initial_threads = None
        self.process = psutil.Process()

    def snapshot(self):
        """Take a snapshot of current resource usage."""
        gc.collect()  # Force garbage collection
        time.sleep(0.1)  # Give OS time to release resources

        return {
            'handles': self.process.num_handles() if sys.platform == 'win32' else 0,
            'memory': self.process.memory_info().rss,
            'threads': self.process.num_threads(),
        }

    def start_tracking(self):
        """Start tracking resources."""
        self.initial_handles = self.snapshot()['handles']
        self.initial_memory = self.snapshot()['memory']
        self.initial_threads = self.snapshot()['threads']

    def check_leaks(self, tolerance_pct=10):
        """
        Check for resource leaks.

        Args:
            tolerance_pct: Percentage tolerance for resource increases

        Returns:
            dict: Resource leak information
        """
        current = self.snapshot()

        # Calculate percentage increases
        handle_increase = 0
        if self.initial_handles > 0:
            handle_increase = ((current['handles'] - self.initial_handles) /
                             self.initial_handles * 100)

        memory_increase = ((current['memory'] - self.initial_memory) /
                          self.initial_memory * 100)

        thread_increase = 0
        if self.initial_threads > 0:
            thread_increase = ((current['threads'] - self.initial_threads) /
                             self.initial_threads * 100)

        return {
            'handles': {
                'initial': self.initial_handles,
                'current': current['handles'],
                'increase_pct': handle_increase,
                'leaked': handle_increase > tolerance_pct
            },
            'memory': {
                'initial': self.initial_memory,
                'current': current['memory'],
                'increase_pct': memory_increase,
                'leaked': memory_increase > tolerance_pct
            },
            'threads': {
                'initial': self.initial_threads,
                'current': current['threads'],
                'increase_pct': thread_increase,
                'leaked': thread_increase > tolerance_pct
            }
        }


@contextmanager
def resource_leak_detector(tolerance_pct=10):
    """
    Context manager to detect resource leaks.

    Usage:
        with resource_leak_detector() as tracker:
            # Code that should not leak resources
            pass
        assert not tracker.check_leaks()['handles']['leaked']
    """
    tracker = ResourceTracker()
    tracker.start_tracking()
    yield tracker
    # Leak check happens in the test after context exit


def wait_for_condition(condition: Callable[[], bool], timeout: float = 5.0,
                       check_interval: float = 0.1) -> bool:
    """
    Wait for a condition to become true.

    Args:
        condition: Function that returns bool
        timeout: Maximum time to wait in seconds
        check_interval: How often to check the condition

    Returns:
        True if condition became true, False if timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition():
            return True
        time.sleep(check_interval)
    return False


def cleanup_processes_by_name(name: str):
    """
    Kill all processes with a given name.
    Useful for cleaning up test processes.
    """
    for proc in psutil.process_iter(['name', 'pid']):
        try:
            if proc.info['name'] and name.lower() in proc.info['name'].lower():
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def get_open_file_count() -> int:
    """
    Get the number of open file handles for the current process.
    """
    process = psutil.Process()
    try:
        return len(process.open_files())
    except (psutil.AccessDenied, AttributeError):
        return 0


def measure_execution_time(func: Callable, *args, **kwargs) -> tuple[Any, float]:
    """
    Measure execution time of a function.

    Returns:
        Tuple of (result, execution_time_seconds)
    """
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    execution_time = time.perf_counter() - start_time
    return result, execution_time


class TimeoutException(Exception):
    """Raised when an operation times out."""
    pass


def run_with_timeout(func: Callable, timeout: float, *args, **kwargs) -> Any:
    """
    Run a function with a timeout.

    Args:
        func: Function to run
        timeout: Timeout in seconds
        *args, **kwargs: Arguments for the function

    Returns:
        Function result

    Raises:
        TimeoutException: If function doesn't complete in time
    """
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutException(f"Function {func.__name__} timed out after {timeout}s")


def create_test_script(script_dir: Path, name: str, content: str) -> Path:
    """
    Create a test script file.

    Args:
        script_dir: Directory to create script in
        name: Script filename (without .py extension)
        content: Script content

    Returns:
        Path to created script
    """
    script_path = script_dir / f"{name}.py"
    script_path.write_text(content, encoding='utf-8')
    return script_path


def verify_json_output(output: str) -> tuple[bool, Optional[dict]]:
    """
    Verify that output is valid JSON and parse it.

    Returns:
        Tuple of (is_valid, parsed_data)
    """
    import json

    try:
        data = json.loads(output)
        return True, data
    except (json.JSONDecodeError, ValueError):
        return False, None


def mock_windows_api_error(error_code: int = 5):
    """
    Create a mock Windows API error.

    Args:
        error_code: Windows error code (default 5 = Access Denied)
    """
    if sys.platform == 'win32':
        import pywintypes
        return pywintypes.error(error_code, 'MockWindowsAPIFunction', 'Mock error message')
    else:
        return Exception(f"Mock Windows error: {error_code}")


class QTimerSpy:
    """
    Helper to spy on QTimer behavior in tests.
    """

    def __init__(self, timer):
        self.timer = timer
        self.started = False
        self.stopped = False
        self.timeout_count = 0

        # Connect to timer signals
        self.timer.timeout.connect(self._on_timeout)

    def _on_timeout(self):
        self.timeout_count += 1

    def reset(self):
        """Reset spy counters."""
        self.started = False
        self.stopped = False
        self.timeout_count = 0


def assert_signal_emitted(signal_spy, expected_count: int = None, timeout: float = 1.0):
    """
    Assert that a signal was emitted a certain number of times.

    Args:
        signal_spy: QSignalSpy instance
        expected_count: Expected number of emissions (None = at least 1)
        timeout: Time to wait for signal
    """
    if expected_count is None:
        # Wait for at least one emission
        if not wait_for_condition(lambda: len(signal_spy) > 0, timeout=timeout):
            raise AssertionError(f"Signal was not emitted within {timeout}s")
    else:
        # Wait for exact count
        if not wait_for_condition(lambda: len(signal_spy) == expected_count, timeout=timeout):
            raise AssertionError(
                f"Expected {expected_count} signal emissions, got {len(signal_spy)}"
            )


def stress_test_operation(operation: Callable, iterations: int = 100, concurrency: int = 1):
    """
    Stress test an operation by running it many times.

    Args:
        operation: Function to stress test
        iterations: Number of times to run
        concurrency: Number of concurrent threads (default 1 = sequential)

    Returns:
        Dict with results including success count, failure count, and exceptions
    """
    import concurrent.futures
    from collections import Counter

    results = {
        'success': 0,
        'failure': 0,
        'exceptions': Counter(),
        'total_time': 0
    }

    start_time = time.perf_counter()

    if concurrency == 1:
        # Sequential execution
        for _ in range(iterations):
            try:
                operation()
                results['success'] += 1
            except Exception as e:
                results['failure'] += 1
                results['exceptions'][type(e).__name__] += 1
    else:
        # Concurrent execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(operation) for _ in range(iterations)]

            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                    results['success'] += 1
                except Exception as e:
                    results['failure'] += 1
                    results['exceptions'][type(e).__name__] += 1

    results['total_time'] = time.perf_counter() - start_time

    return results
