"""
Pytest configuration and shared fixtures for BindKit tests.
"""
import pytest
import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try to import and setup PyQt6, but gracefully handle cases where display is not available
try:
    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtWidgets import QApplication
    QT_AVAILABLE = True
except (ImportError, RuntimeError) as e:
    QT_AVAILABLE = False
    QApplication = None
    QCoreApplication = None


@pytest.fixture(scope="session")
def qapp():
    """
    Session-wide QApplication instance.
    Required for any tests that use Qt components.
    Skips if PyQt6 is not available (e.g., in headless environments).
    """
    if not QT_AVAILABLE:
        pytest.skip("PyQt6 not available in this environment")

    app = QCoreApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Don't quit the app, as it may be needed for other tests


@pytest.fixture
def temp_dir():
    """
    Create a temporary directory for test files.
    Automatically cleaned up after the test.
    """
    temp_path = tempfile.mkdtemp(prefix="bindkit_test_")
    yield Path(temp_path)
    # Cleanup
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_scripts_dir(temp_dir):
    """
    Create a temporary scripts directory with proper structure.
    """
    scripts_path = temp_dir / "scripts"
    scripts_path.mkdir(parents=True, exist_ok=True)
    return scripts_path


@pytest.fixture
def temp_logs_dir(temp_dir):
    """
    Create a temporary logs directory.
    """
    logs_path = temp_dir / "logs"
    logs_path.mkdir(parents=True, exist_ok=True)
    return logs_path


@pytest.fixture
def mock_settings():
    """
    Create a mock SettingsManager for tests that don't need real persistence.
    """
    settings = Mock()
    settings.get = Mock(return_value=None)
    settings.set = Mock()
    settings.sync = Mock()
    settings.get_disabled_scripts = Mock(return_value=[])
    settings.get_external_scripts = Mock(return_value={})
    settings.get_status_refresh_seconds = Mock(return_value=5)
    settings.get_script_timeout_seconds = Mock(return_value=30)
    settings.settings = MagicMock()
    return settings


@pytest.fixture
def sample_script_simple(temp_scripts_dir):
    """
    Create a simple test script that outputs JSON.
    """
    script_path = temp_scripts_dir / "simple_test.py"
    script_content = '''#!/usr/bin/env python3
import json

if __name__ == '__main__':
    print(json.dumps({"success": True, "message": "Simple test executed"}))
'''
    script_path.write_text(script_content)
    return script_path


@pytest.fixture
def sample_script_with_args(temp_scripts_dir):
    """
    Create a test script with argparse arguments.
    """
    script_path = temp_scripts_dir / "args_test.py"
    script_content = '''#!/usr/bin/env python3
import argparse
import json

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Test script with arguments')
    parser.add_argument('--name', type=str, required=True, help='Name parameter')
    parser.add_argument('--count', type=int, default=1, help='Count parameter')
    args = parser.parse_args()

    print(json.dumps({
        "success": True,
        "message": f"Executed with name={args.name}, count={args.count}"
    }))
'''
    script_path.write_text(script_content)
    return script_path


@pytest.fixture
def sample_script_function(temp_scripts_dir):
    """
    Create a script with a main() function (FUNCTION_CALL strategy).
    """
    script_path = temp_scripts_dir / "function_test.py"
    script_content = '''#!/usr/bin/env python3
import json

def main():
    return {"success": True, "message": "Function call executed"}

if __name__ == '__main__':
    result = main()
    print(json.dumps(result))
'''
    script_path.write_text(script_content)
    return script_path


@pytest.fixture
def sample_script_error(temp_scripts_dir):
    """
    Create a script that raises an error.
    """
    script_path = temp_scripts_dir / "error_test.py"
    script_content = '''#!/usr/bin/env python3
if __name__ == '__main__':
    raise RuntimeError("Intentional test error")
'''
    script_path.write_text(script_content)
    return script_path


@pytest.fixture
def sample_script_timeout(temp_scripts_dir):
    """
    Create a script that sleeps for a long time (for timeout tests).
    """
    script_path = temp_scripts_dir / "timeout_test.py"
    script_content = '''#!/usr/bin/env python3
import time
if __name__ == '__main__':
    time.sleep(3600)  # Sleep for 1 hour
'''
    script_path.write_text(script_content)
    return script_path


@pytest.fixture
def sample_script_invalid_json(temp_scripts_dir):
    """
    Create a script that outputs invalid JSON.
    """
    script_path = temp_scripts_dir / "invalid_json_test.py"
    script_content = '''#!/usr/bin/env python3
if __name__ == '__main__':
    print("This is not JSON")
'''
    script_path.write_text(script_content)
    return script_path


@pytest.fixture
def sample_script_empty(temp_scripts_dir):
    """
    Create an empty script file.
    """
    script_path = temp_scripts_dir / "empty_test.py"
    script_path.write_text("")
    return script_path


@pytest.fixture
def sample_script_syntax_error(temp_scripts_dir):
    """
    Create a script with syntax errors.
    """
    script_path = temp_scripts_dir / "syntax_error_test.py"
    script_content = '''#!/usr/bin/env python3
def broken syntax here
    invalid python code
'''
    script_path.write_text(script_content)
    return script_path


@pytest.fixture
def sample_script_unicode(temp_scripts_dir):
    """
    Create a script with Unicode content.
    """
    script_path = temp_scripts_dir / "unicode_test.py"
    script_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

if __name__ == '__main__':
    print(json.dumps({
        "success": True,
        "message": "Unicode test: こんにちは 世界 🌍 Ñoño"
    }))
'''
    script_path.write_text(script_content, encoding='utf-8')
    return script_path


@pytest.fixture
def sample_script_service(temp_scripts_dir):
    """
    Create a long-running service script.
    """
    script_path = temp_scripts_dir / "service_test.py"
    script_content = '''#!/usr/bin/env python3
"""
A long-running service script for testing.

Service: True
"""
import time
import json

if __name__ == '__main__':
    print(json.dumps({"success": True, "message": "Service started"}))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(json.dumps({"success": True, "message": "Service stopped"}))
'''
    script_path.write_text(script_content)
    return script_path


@pytest.fixture
def sample_script_scheduled(temp_scripts_dir):
    """
    Create a scheduled script.
    """
    script_path = temp_scripts_dir / "scheduled_test.py"
    script_content = '''#!/usr/bin/env python3
"""
A scheduled script for testing.

Schedule: 60
"""
import json
import time

if __name__ == '__main__':
    print(json.dumps({
        "success": True,
        "message": f"Scheduled execution at {time.time()}"
    }))
'''
    script_path.write_text(script_content)
    return script_path


def pytest_configure(config):
    """
    Configure pytest with custom settings.
    """
    # Register custom markers
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual components"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests across components"
    )
    config.addinivalue_line(
        "markers", "windows: Windows-specific tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow-running tests"
    )
    config.addinivalue_line(
        "markers", "race_condition: Tests for race conditions"
    )
    config.addinivalue_line(
        "markers", "resource_leak: Tests for resource leaks"
    )
    config.addinivalue_line(
        "markers", "edge_case: Edge case tests"
    )
