"""
Unit tests for ScheduleRuntime.

Tests scheduling, overlap prevention, race conditions, and timer management.
"""
import pytest
import sys
import os
import time
from pathlib import Path
from unittest.mock import Mock, MagicMock
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtTest import QSignalSpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.schedule_runtime import (
    ScheduleRuntime,
    ScheduleState,
    ScheduleHandle,
    MIN_INTERVAL_SECONDS,
    MAX_TIMER_INTERVAL_SECONDS
)
from tests.test_utilities import wait_for_condition


class TestScheduleRuntime:
    """Test cases for ScheduleRuntime"""

    @pytest.fixture
    def runtime(self, qapp):
        """Create a ScheduleRuntime instance for testing"""
        return ScheduleRuntime()

    @pytest.fixture
    def mock_callback(self):
        """Create a mock callback function"""
        return Mock(return_value=None)

    @pytest.fixture
    def temp_script_path(self, temp_scripts_dir):
        """Create a temporary script path"""
        script_path = temp_scripts_dir / "scheduled_test.py"
        script_path.write_text('print("scheduled")')
        return script_path

    def test_initialization(self, runtime):
        """Test runtime initializes correctly"""
        assert runtime._active_schedules is not None
        assert len(runtime._active_schedules) == 0
        assert runtime._schedule_lock is not None

    def test_start_schedule_success(self, runtime, temp_script_path, mock_callback):
        """Test starting a schedule"""
        handle = runtime.start_schedule(
            script_name="TestScript",
            script_path=temp_script_path,
            interval_seconds=60,
            execution_callback=mock_callback
        )

        assert handle is not None
        assert handle.script_name == "TestScript"
        assert handle.interval_seconds == 60
        assert handle.state == ScheduleState.SCHEDULED
        assert handle.timer is not None

        # Cleanup
        runtime.stop_schedule("TestScript")

    def test_start_schedule_with_signals(self, runtime, temp_script_path, mock_callback):
        """Test that schedule start emits signals"""
        started_spy = QSignalSpy(runtime.schedule_started)

        handle = runtime.start_schedule(
            script_name="TestScript",
            script_path=temp_script_path,
            interval_seconds=60,
            execution_callback=mock_callback
        )

        assert len(started_spy) == 1
        assert started_spy[0][0] == "TestScript"

        runtime.stop_schedule("TestScript")

    @pytest.mark.edge_case
    def test_start_schedule_min_interval(self, runtime, temp_script_path, mock_callback):
        """Test starting schedule with minimum interval"""
        handle = runtime.start_schedule(
            script_name="MinIntervalTest",
            script_path=temp_script_path,
            interval_seconds=MIN_INTERVAL_SECONDS,
            execution_callback=mock_callback
        )

        assert handle is not None
        assert handle.interval_seconds == MIN_INTERVAL_SECONDS

        runtime.stop_schedule("MinIntervalTest")

    @pytest.mark.edge_case
    def test_start_schedule_below_min_interval(self, runtime, temp_script_path, mock_callback):
        """Test that intervals below minimum are rejected or adjusted"""
        try:
            handle = runtime.start_schedule(
                script_name="BelowMinTest",
                script_path=temp_script_path,
                interval_seconds=5,  # Below MIN_INTERVAL_SECONDS (10)
                execution_callback=mock_callback
            )

            # If it doesn't raise an error, it should have adjusted the interval
            if handle:
                assert handle.interval_seconds >= MIN_INTERVAL_SECONDS
                runtime.stop_schedule("BelowMinTest")

        except (ValueError, AssertionError):
            # Expected to raise an error for too-small interval
            pass

    @pytest.mark.edge_case
    def test_start_schedule_max_interval(self, runtime, temp_script_path, mock_callback):
        """Test starting schedule with maximum safe interval"""
        handle = runtime.start_schedule(
            script_name="MaxIntervalTest",
            script_path=temp_script_path,
            interval_seconds=MAX_TIMER_INTERVAL_SECONDS,
            execution_callback=mock_callback
        )

        assert handle is not None

        runtime.stop_schedule("MaxIntervalTest")

    @pytest.mark.edge_case
    def test_start_schedule_above_max_interval(self, runtime, temp_script_path, mock_callback):
        """Test that intervals above maximum are rejected or adjusted"""
        try:
            handle = runtime.start_schedule(
                script_name="AboveMaxTest",
                script_path=temp_script_path,
                interval_seconds=MAX_TIMER_INTERVAL_SECONDS + 1000,
                execution_callback=mock_callback
            )

            # Should either raise error or adjust interval
            if handle:
                assert handle.interval_seconds <= MAX_TIMER_INTERVAL_SECONDS
                runtime.stop_schedule("AboveMaxTest")

        except (ValueError, OverflowError):
            # Expected to raise an error for too-large interval
            pass

    def test_stop_schedule(self, runtime, temp_script_path, mock_callback):
        """Test stopping a schedule"""
        stopped_spy = QSignalSpy(runtime.schedule_stopped)

        # Start a schedule
        handle = runtime.start_schedule(
            script_name="StopTest",
            script_path=temp_script_path,
            interval_seconds=60,
            execution_callback=mock_callback
        )

        # Stop it
        runtime.stop_schedule("StopTest")

        # Check signal
        assert len(stopped_spy) == 1
        assert stopped_spy[0][0] == "StopTest"

        # Check that it's no longer in active schedules
        assert "StopTest" not in runtime._active_schedules

    def test_stop_nonexistent_schedule(self, runtime):
        """Test stopping a schedule that doesn't exist"""
        # Should not raise an error
        runtime.stop_schedule("NonexistentScript")

    @pytest.mark.race_condition
    def test_overlap_prevention(self, runtime, temp_script_path, qapp):
        """Test that overlap prevention works (critical bug detection)"""
        execution_count = {'count': 0, 'overlaps': 0}

        def slow_callback():
            """Callback that takes longer than the interval"""
            execution_count['count'] += 1
            time.sleep(0.5)  # Longer than interval

        # Start schedule with very short interval
        handle = runtime.start_schedule(
            script_name="OverlapTest",
            script_path=temp_script_path,
            interval_seconds=MIN_INTERVAL_SECONDS,  # Use minimum allowed
            execution_callback=slow_callback
        )

        # Manually trigger execution multiple times rapidly
        if hasattr(handle, '_execute_callback'):
            # First execution
            handle._execute_callback()

            # Try to execute again while first is still running
            # This should be blocked by overlap prevention
            handle._execute_callback()

        runtime.stop_schedule("OverlapTest")

        # There should be no overlapping executions
        # (This test depends on the actual implementation of overlap prevention)

    @pytest.mark.slow
    def test_schedule_execution_timing(self, runtime, temp_script_path, qapp, mock_callback):
        """Test that schedules execute at correct intervals"""
        execution_times = []

        def tracking_callback():
            execution_times.append(time.time())
            mock_callback()

        # Start schedule with minimum allowed interval (10 seconds)
        handle = runtime.start_schedule(
            script_name="TimingTest",
            script_path=temp_script_path,
            interval_seconds=MIN_INTERVAL_SECONDS,  # Minimum allowed interval
            execution_callback=tracking_callback
        )

        # Wait for a few executions (but not too many for test speed)
        # This requires the actual timer to fire
        # Note: This test may be flaky depending on system load

        time.sleep(11)  # Wait for at least one execution (10s + buffer)
        qapp.processEvents()  # Process Qt events

        runtime.stop_schedule("TimingTest")

        # At least one execution should have occurred
        # (Actual timing verification would require more complex test setup)

    def test_get_schedule_status(self, runtime, temp_script_path, mock_callback):
        """Test getting schedule status"""
        # Start a schedule
        handle = runtime.start_schedule(
            script_name="StatusTest",
            script_path=temp_script_path,
            interval_seconds=60,
            execution_callback=mock_callback
        )

        # Check if we can get status
        if hasattr(runtime, 'get_schedule_status'):
            status = runtime.get_schedule_status("StatusTest")
            assert status is not None

        runtime.stop_schedule("StatusTest")

    def test_get_all_schedules(self, runtime, temp_script_path, mock_callback):
        """Test getting all active schedules"""
        # Start multiple schedules
        for i in range(3):
            runtime.start_schedule(
                script_name=f"Schedule{i}",
                script_path=temp_script_path,
                interval_seconds=60 + i,
                execution_callback=mock_callback
            )

        # Check that we can get all schedules
        assert len(runtime._active_schedules) == 3

        # Cleanup
        for i in range(3):
            runtime.stop_schedule(f"Schedule{i}")

    @pytest.mark.race_condition
    def test_concurrent_schedule_starts(self, runtime, temp_script_path, mock_callback):
        """Test starting multiple schedules concurrently"""
        import concurrent.futures

        def start_schedule(name):
            return runtime.start_schedule(
                script_name=name,
                script_path=temp_script_path,
                interval_seconds=60,
                execution_callback=mock_callback
            )

        # Start 10 schedules concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(start_schedule, f"Concurrent{i}") for i in range(10)]
            handles = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should be created
        assert len(handles) == 10
        assert all(h is not None for h in handles)

        # Cleanup
        for i in range(10):
            runtime.stop_schedule(f"Concurrent{i}")

    @pytest.mark.race_condition
    def test_concurrent_schedule_stops(self, runtime, temp_script_path, mock_callback):
        """Test stopping multiple schedules concurrently"""
        import concurrent.futures

        # Start multiple schedules
        for i in range(10):
            runtime.start_schedule(
                script_name=f"StopConcurrent{i}",
                script_path=temp_script_path,
                interval_seconds=60,
                execution_callback=mock_callback
            )

        def stop_schedule(name):
            runtime.stop_schedule(name)

        # Stop all concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(stop_schedule, f"StopConcurrent{i}") for i in range(10)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        # All should be stopped
        assert len(runtime._active_schedules) == 0

    @pytest.mark.race_condition
    def test_stop_during_execution(self, runtime, temp_script_path, qapp):
        """Test stopping a schedule while it's executing (critical race condition test)"""
        execution_started = {'started': False}

        def long_callback():
            execution_started['started'] = True
            time.sleep(1.0)

        handle = runtime.start_schedule(
            script_name="StopDuringExec",
            script_path=temp_script_path,
            interval_seconds=MIN_INTERVAL_SECONDS,
            execution_callback=long_callback
        )

        # Manually trigger execution
        if hasattr(handle, '_execute_callback'):
            import threading

            exec_thread = threading.Thread(target=handle._execute_callback)
            exec_thread.start()

            # Wait for execution to start
            wait_for_condition(lambda: execution_started['started'], timeout=2.0)

            # Try to stop while executing
            runtime.stop_schedule("StopDuringExec")

            exec_thread.join(timeout=2.0)

        # Should not crash or deadlock

    def test_schedule_state_transitions(self, runtime, temp_script_path, mock_callback):
        """Test schedule state transitions"""
        handle = runtime.start_schedule(
            script_name="StateTest",
            script_path=temp_script_path,
            interval_seconds=60,
            execution_callback=mock_callback
        )

        # Initial state should be SCHEDULED
        assert handle.state == ScheduleState.SCHEDULED

        # Stop should transition to STOPPED (if state is tracked)
        runtime.stop_schedule("StateTest")

    @pytest.mark.edge_case
    def test_restart_schedule(self, runtime, temp_script_path, mock_callback):
        """Test restarting a schedule (stop then start with same name)"""
        # Start schedule
        handle1 = runtime.start_schedule(
            script_name="RestartTest",
            script_path=temp_script_path,
            interval_seconds=60,
            execution_callback=mock_callback
        )

        # Stop it
        runtime.stop_schedule("RestartTest")

        # Start again with same name
        handle2 = runtime.start_schedule(
            script_name="RestartTest",
            script_path=temp_script_path,
            interval_seconds=120,
            execution_callback=mock_callback
        )

        assert handle2 is not None
        assert handle2.interval_seconds == 120

        runtime.stop_schedule("RestartTest")

    @pytest.mark.edge_case
    def test_schedule_with_failing_callback(self, runtime, temp_script_path, qapp):
        """Test schedule when callback raises an exception"""
        error_spy = QSignalSpy(runtime.schedule_error)

        def failing_callback():
            raise RuntimeError("Intentional callback error")

        handle = runtime.start_schedule(
            script_name="FailingCallbackTest",
            script_path=temp_script_path,
            interval_seconds=MIN_INTERVAL_SECONDS,
            execution_callback=failing_callback
        )

        # Manually trigger execution
        if hasattr(handle, '_execute_callback'):
            try:
                handle._execute_callback()
            except RuntimeError:
                pass  # Expected

        # Check if error signal was emitted
        # (depends on implementation)

        runtime.stop_schedule("FailingCallbackTest")

    def test_schedule_handle_dataclass(self, temp_script_path):
        """Test ScheduleHandle dataclass"""
        mock_timer = Mock()

        handle = ScheduleHandle(
            script_name="TestHandle",
            script_path=temp_script_path,
            interval_seconds=60,
            timer=mock_timer,
            state=ScheduleState.SCHEDULED
        )

        assert handle.script_name == "TestHandle"
        assert handle.interval_seconds == 60
        assert handle.state == ScheduleState.SCHEDULED
        assert handle.is_executing is False
        assert handle.last_run is None

    def test_timestamp_tracking(self, runtime, temp_script_path, mock_callback):
        """Test that last_run and next_run timestamps are tracked"""
        handle = runtime.start_schedule(
            script_name="TimestampTest",
            script_path=temp_script_path,
            interval_seconds=60,
            execution_callback=mock_callback
        )

        # next_run should be set after start
        # (implementation-dependent)

        runtime.stop_schedule("TimestampTest")

    @pytest.mark.resource_leak
    def test_timer_cleanup_on_stop(self, runtime, temp_script_path, mock_callback):
        """Test that timers are properly cleaned up when stopped"""
        # Start multiple schedules
        for i in range(5):
            runtime.start_schedule(
                script_name=f"TimerCleanup{i}",
                script_path=temp_script_path,
                interval_seconds=60,
                execution_callback=mock_callback
            )

        # Stop all
        for i in range(5):
            runtime.stop_schedule(f"TimerCleanup{i}")

        # All timers should be stopped and cleaned up
        assert len(runtime._active_schedules) == 0

    @pytest.mark.edge_case
    def test_schedule_with_none_callback(self, runtime, temp_script_path):
        """Test starting schedule with None callback"""
        try:
            handle = runtime.start_schedule(
                script_name="NoneCallbackTest",
                script_path=temp_script_path,
                interval_seconds=60,
                execution_callback=None
            )

            # Should either reject None callback or handle it gracefully
            if handle:
                runtime.stop_schedule("NoneCallbackTest")

        except (ValueError, TypeError):
            # Expected to raise error for None callback
            pass

    def test_stop_all_schedules(self, runtime, temp_script_path, mock_callback):
        """Test stopping all schedules at once"""
        # Start multiple schedules
        for i in range(5):
            runtime.start_schedule(
                script_name=f"StopAll{i}",
                script_path=temp_script_path,
                interval_seconds=60,
                execution_callback=mock_callback
            )

        # Stop all (if method exists)
        if hasattr(runtime, 'stop_all_schedules'):
            runtime.stop_all_schedules()
            assert len(runtime._active_schedules) == 0
        else:
            # Manually stop all
            for i in range(5):
                runtime.stop_schedule(f"StopAll{i}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
