# BindKit Test Suite

Comprehensive test suite for BindKit designed to expose bugs, race conditions, and edge cases.

## Overview

This test suite includes:
- **Unit tests** for core components
- **Edge case tests** for unusual inputs and boundary conditions
- **Race condition tests** for concurrent operations
- **Resource leak tests** for memory and handle cleanup
- **Windows-specific tests** for Win32 API integration

## Test Files

### Core Component Tests

- `test_script_analyzer.py` - AST parsing, execution strategy detection, edge cases
- `test_script_executor.py` - Script execution, module caching, timeout handling
- `test_script_loader.py` - Script discovery, parallel loading, error handling
- `test_schedule_runtime.py` - Scheduled execution, overlap prevention, timer management
- `test_hotkey_registry.py` - Hotkey persistence, validation, duplicate detection

### Model Tests (Existing)

- `test_script_models.py` - Script collection, execution, and hotkey models
- `test_application_model.py` - Application state management

### Special Test Categories

- `test_edge_cases.py` - Unicode, invalid inputs, resource limits, timing edge cases
- `test_race_conditions.py` - Concurrent operations, deadlock detection, data races

### Test Infrastructure

- `conftest.py` - Pytest fixtures and configuration
- `test_utilities.py` - Helper functions and utilities

## Running Tests

### Run All Tests

```bash
pytest
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest tests/test_script_analyzer.py
```

### Run Tests by Marker

```bash
# Run only unit tests
pytest -m unit

# Run only edge case tests
pytest -m edge_case

# Run only race condition tests
pytest -m race_condition

# Run only Windows-specific tests
pytest -m windows

# Run only slow tests
pytest -m slow

# Skip slow tests
pytest -m "not slow"

# Run resource leak tests
pytest -m resource_leak
```

### Run with Coverage

```bash
# Install pytest-cov if needed
pip install pytest-cov

# Run with coverage report
pytest --cov=core --cov=models --cov=controllers --cov-report=html --cov-report=term
```

### Run in Parallel

```bash
# Install pytest-xdist if needed
pip install pytest-xdist

# Run tests in parallel (faster)
pytest -n auto
```

## Test Markers

Tests are categorized with markers:

- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.integration` - Integration tests across components
- `@pytest.mark.windows` - Windows-specific tests (Win32 API, Registry, etc.)
- `@pytest.mark.slow` - Tests that take significant time to run
- `@pytest.mark.race_condition` - Tests that check for race conditions
- `@pytest.mark.resource_leak` - Tests that check for resource leaks
- `@pytest.mark.edge_case` - Tests for edge cases and unusual inputs

## Bug Categories Tested

### Race Conditions

- Concurrent script loading and execution
- Parallel hotkey registration/removal
- Schedule overlap prevention
- Module cache cleanup during execution
- Timer modification from multiple threads
- Deadlock detection in registry and executor

### Resource Leaks

- File handle leaks
- Process cleanup (Win32 job objects)
- Module cache TTL/LRU eviction
- QTimer cleanup on schedule stop
- Memory leaks in long-running operations

### Edge Cases

#### Unicode and Encoding
- Scripts with emoji in output
- Right-to-Left text (Arabic, Hebrew)
- Mixed writing systems (Cyrillic, Greek, Chinese, Japanese, Korean)
- Unicode in filenames and paths
- UTF-8 BOM handling

#### Path Edge Cases
- Very deep directory nesting
- Paths with spaces
- Paths with special characters
- Unicode paths
- Long paths (>260 chars on Windows)

#### Input Validation
- Empty/None values
- Very long arguments (10MB+)
- Zero-length arguments
- Scripts with many arguments (100+)
- Invalid JSON output
- Malformed data

#### Timing Edge Cases
- Scripts that execute in microseconds
- Scripts with infinite loops (timeout testing)
- Rapid start/stop operations
- Concurrent timer modifications

#### Output Edge Cases
- Scripts with no output
- Scripts that only write to stderr
- Scripts with binary output
- Scripts with malformed JSON
- Very long output (millions of characters)

### Error Handling

- Syntax errors in scripts
- Missing required arguments
- Import errors (non-existent modules)
- Runtime exceptions
- Permission errors
- File not found errors
- Invalid script formats

### Windows-Specific

- Win32 API error handling
- Registry permission errors
- Process creation failures
- Job object limits
- Handle cleanup verification
- Signal handling (CTRL_BREAK_EVENT)

## Test Fixtures

Common fixtures available in `conftest.py`:

- `qapp` - QApplication instance for Qt tests
- `temp_dir` - Temporary directory (auto-cleaned)
- `temp_scripts_dir` - Temporary scripts directory
- `temp_logs_dir` - Temporary logs directory
- `mock_settings` - Mock SettingsManager
- `sample_script_*` - Various pre-made test scripts

## Test Utilities

Helper functions in `test_utilities.py`:

- `ResourceTracker` - Track and detect resource leaks
- `resource_leak_detector()` - Context manager for leak detection
- `wait_for_condition()` - Wait for async conditions
- `cleanup_processes_by_name()` - Kill test processes
- `measure_execution_time()` - Measure function execution time
- `run_with_timeout()` - Run function with timeout
- `create_test_script()` - Create test script files
- `verify_json_output()` - Validate JSON output
- `stress_test_operation()` - Stress test an operation

## Continuous Integration

To integrate with CI/CD:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -r requirements.txt
    pip install pytest pytest-cov pytest-xdist
    pytest -v --cov=core --cov=models --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Expected Test Outcomes

The test suite is designed to:

1. **Expose bugs** through unusual inputs and edge cases
2. **Detect race conditions** through concurrent operations
3. **Find resource leaks** through repeated operations
4. **Verify error handling** through invalid inputs
5. **Test Windows integration** through API mocking and real calls

Not all tests may pass initially - they are designed to find bugs!

## Adding New Tests

When adding new tests:

1. Place them in the appropriate test file or create a new one
2. Use descriptive test names: `test_<what_is_being_tested>`
3. Add appropriate markers: `@pytest.mark.edge_case`, etc.
4. Use fixtures from `conftest.py` when possible
5. Document what bug the test is trying to expose
6. Clean up resources (use fixtures with yield)

Example:

```python
@pytest.mark.edge_case
def test_script_with_unicode_emoji(self, temp_scripts_dir, mock_settings):
    """Test that scripts can output emoji characters without crashing"""
    script_content = '''
import json
print(json.dumps({"emoji": "🎉"}))
'''
    script_path = create_test_script(temp_scripts_dir, 'emoji_test', script_content)

    analyzer = ScriptAnalyzer()
    script_info = analyzer.analyze_script(script_path)

    assert script_info.is_executable

    executor = ScriptExecutor(mock_settings)
    result = executor.execute_script(script_info)

    assert result.success
```

## Troubleshooting

### Tests Hang

- Check for deadlocks in race condition tests
- Reduce concurrency in parallel tests
- Add timeouts to long-running operations

### Tests Fail Intermittently

- Likely race condition - increase wait times
- Check for timing-dependent assertions
- Reduce system load during testing

### Import Errors

- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python path configuration
- Verify pytest is finding the project root

### Windows-Specific Test Failures

- Some tests may require administrator privileges
- Win32 API tests may fail on non-Windows systems
- Use pytest markers to skip: `pytest -m "not windows"`

## Performance Considerations

- Slow tests are marked with `@pytest.mark.slow`
- Use `pytest -m "not slow"` for quick test runs
- Run slow tests separately in CI/CD
- Consider using `pytest-xdist` for parallel execution

## License

Same as BindKit project.
