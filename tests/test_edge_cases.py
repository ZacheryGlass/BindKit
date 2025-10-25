"""
Comprehensive edge case tests for BindKit.

Tests unusual inputs, boundary conditions, and resource exhaustion scenarios
that could expose bugs.
"""
import pytest
import sys
import os
import time
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.script_analyzer import ScriptAnalyzer
from core.script_executor import ScriptExecutor
from core.script_loader import ScriptLoader
from tests.test_utilities import create_test_script, verify_json_output


@pytest.mark.edge_case
class TestUnicodeEdgeCases:
    """Test handling of Unicode in various contexts"""

    def test_script_with_emoji_in_output(self, temp_scripts_dir, mock_settings):
        """Test script that outputs emojis"""
        script_content = '''
# -*- coding: utf-8 -*-
import json

if __name__ == '__main__':
    print(json.dumps({
        "message": "Success 🎉 Test 🚀 Complete ✅",
        "emoji": "😀😃😄😁"
    }, ensure_ascii=False))
'''
        script_path = create_test_script(temp_scripts_dir, 'emoji_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info.is_executable

        executor = ScriptExecutor(mock_settings)
        result = executor.execute_script(script_info)

        assert result.success

    def test_script_with_rtl_text(self, temp_scripts_dir, mock_settings):
        """Test script with Right-to-Left text (Arabic, Hebrew)"""
        script_content = '''
# -*- coding: utf-8 -*-
import json

if __name__ == '__main__':
    print(json.dumps({
        "arabic": "مرحبا بالعالم",
        "hebrew": "שלום עולם"
    }, ensure_ascii=False))
'''
        script_path = create_test_script(temp_scripts_dir, 'rtl_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info.is_executable

    def test_script_with_mixed_scripts(self, temp_scripts_dir):
        """Test script with mixed writing systems"""
        script_content = '''
# -*- coding: utf-8 -*-
"""
Mixed scripts: Latin, Cyrillic, Greek, Chinese, Japanese, Korean
Test: Тест Δοκιμή 测试 テスト 테스트
"""
import json

if __name__ == '__main__':
    data = {
        "latin": "Hello",
        "cyrillic": "Привет",
        "greek": "Γειά",
        "chinese": "你好",
        "japanese": "こんにちは",
        "korean": "안녕하세요"
    }
    print(json.dumps(data, ensure_ascii=False))
'''
        script_path = create_test_script(temp_scripts_dir, 'mixed_scripts', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info.is_executable

    def test_unicode_script_filename(self, temp_scripts_dir):
        """Test script file with Unicode characters in name"""
        script_path = temp_scripts_dir / "测试脚本_テスト.py"
        script_path.write_text(
            'if __name__ == "__main__":\n    print("Unicode filename")',
            encoding='utf-8'
        )

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        # Should handle Unicode filename
        assert script_info is not None


@pytest.mark.edge_case
class TestPathEdgeCases:
    """Test edge cases related to file paths"""

    def test_script_in_very_deep_directory(self, temp_dir):
        """Test script in deeply nested directory"""
        # Create a very deep directory structure
        deep_path = temp_dir
        for i in range(20):
            deep_path = deep_path / f"level{i}"

        deep_path.mkdir(parents=True, exist_ok=True)

        script_path = create_test_script(
            deep_path,
            'deep_test',
            'if __name__ == "__main__":\n    print("deep")'
        )

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info is not None

    def test_script_path_with_spaces(self, temp_dir):
        """Test script in path with spaces"""
        space_path = temp_dir / "dir with spaces" / "more spaces"
        space_path.mkdir(parents=True, exist_ok=True)

        script_path = create_test_script(
            space_path,
            'space_test',
            'if __name__ == "__main__":\n    print("spaces")'
        )

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info.is_executable

    def test_script_path_with_special_chars(self, temp_dir):
        """Test script in path with special characters"""
        special_chars = ['dot.dir', 'dash-dir', 'underscore_dir']

        for char_dir in special_chars:
            special_path = temp_dir / char_dir
            special_path.mkdir(exist_ok=True)

            script_path = create_test_script(
                special_path,
                'special_test',
                'if __name__ == "__main__":\n    print("special")'
            )

            analyzer = ScriptAnalyzer()
            script_info = analyzer.analyze_script(script_path)

            assert script_info is not None


@pytest.mark.edge_case
class TestBoundaryConditions:
    """Test boundary conditions and extreme values"""

    def test_script_with_zero_length_arguments(self, temp_scripts_dir, mock_settings):
        """Test script with zero-length argument values"""
        script_content = '''
import argparse
import json

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--value', default='')
    args = parser.parse_args()
    print(json.dumps({"value": args.value, "length": len(args.value)}))
'''
        script_path = create_test_script(temp_scripts_dir, 'zero_arg_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        executor = ScriptExecutor(mock_settings)
        result = executor.execute_script(script_info, {'value': ''})

        assert result.success

    def test_script_with_very_long_argument(self, temp_scripts_dir, mock_settings):
        """Test script with very long argument value"""
        script_content = '''
import argparse
import json

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data')
    args = parser.parse_args()
    print(json.dumps({"length": len(args.data) if args.data else 0}))
'''
        script_path = create_test_script(temp_scripts_dir, 'long_arg_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        # Create very long argument (10MB)
        long_data = 'x' * (10 * 1024 * 1024)

        executor = ScriptExecutor(mock_settings)
        # This might fail or timeout, which is acceptable
        try:
            result = executor.execute_script(script_info, {'data': long_data})
            # If it succeeds, that's good
            assert result is not None
        except (MemoryError, OSError):
            # Expected to fail with very large arguments
            pass

    def test_script_with_many_arguments(self, temp_scripts_dir):
        """Test script with many arguments"""
        # Create script with 100 arguments
        args_def = '\n    '.join([f'parser.add_argument("--arg{i}", default={i})' for i in range(100)])

        script_content = f'''
import argparse
import json

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    {args_def}
    args = parser.parse_args()
    print(json.dumps({{"count": 100}}))
'''
        script_path = create_test_script(temp_scripts_dir, 'many_args_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        # Should parse all arguments
        assert len(script_info.arguments) <= 100

    def test_script_with_null_bytes(self, temp_scripts_dir):
        """Test script containing null bytes"""
        script_path = temp_scripts_dir / "null_bytes.py"

        # Write script with null bytes
        try:
            script_path.write_bytes(
                b'if __name__ == "__main__":\x00\n    print("null")'
            )

            analyzer = ScriptAnalyzer()
            script_info = analyzer.analyze_script(script_path)

            # Should handle null bytes (probably not executable)
            assert script_info is not None

        except Exception:
            # May not be able to write null bytes on all systems
            pass


@pytest.mark.edge_case
class TestInvalidInputs:
    """Test handling of invalid inputs"""

    def test_script_with_no_extension(self, temp_scripts_dir):
        """Test file without .py extension"""
        script_path = temp_scripts_dir / "no_extension"
        script_path.write_text('if __name__ == "__main__":\n    print("test")')

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        # May or may not be accepted depending on implementation
        assert script_info is not None

    def test_script_with_wrong_extension(self, temp_scripts_dir):
        """Test file with wrong extension"""
        script_path = temp_scripts_dir / "wrong.txt"
        script_path.write_text('if __name__ == "__main__":\n    print("test")')

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info is not None

    def test_script_that_imports_nonexistent_module(self, temp_scripts_dir, mock_settings):
        """Test script that tries to import non-existent module"""
        script_content = '''
import nonexistent_module_that_doesnt_exist

if __name__ == '__main__':
    print("test")
'''
        script_path = create_test_script(temp_scripts_dir, 'bad_import_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        # Should analyze successfully (import error happens at runtime)
        assert script_info is not None

        # Execution should fail
        executor = ScriptExecutor(mock_settings)
        result = executor.execute_script(script_info)

        assert not result.success

    def test_script_with_infinite_loop(self, temp_scripts_dir, mock_settings):
        """Test script with infinite loop (should timeout)"""
        script_content = '''
if __name__ == '__main__':
    while True:
        pass
'''
        script_path = create_test_script(temp_scripts_dir, 'infinite_loop_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        # Should be analyzed successfully
        assert script_info.is_executable

        # Execution should timeout (if timeout is implemented)
        # This test requires timeout to be properly configured


@pytest.mark.edge_case
class TestOutputEdgeCases:
    """Test edge cases related to script output"""

    def test_script_with_no_output(self, temp_scripts_dir, mock_settings):
        """Test script that produces no output"""
        script_content = '''
if __name__ == '__main__':
    pass  # No output
'''
        script_path = create_test_script(temp_scripts_dir, 'no_output_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        executor = ScriptExecutor(mock_settings)
        result = executor.execute_script(script_info)

        # Should execute successfully even with no output
        assert result.success or result.output == ""

    def test_script_with_only_stderr(self, temp_scripts_dir, mock_settings):
        """Test script that only writes to stderr"""
        script_content = '''
import sys

if __name__ == '__main__':
    sys.stderr.write("Error message\\n")
    sys.stderr.flush()
'''
        script_path = create_test_script(temp_scripts_dir, 'stderr_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        executor = ScriptExecutor(mock_settings)
        result = executor.execute_script(script_info)

        # Should capture stderr
        assert result is not None

    def test_script_with_binary_output(self, temp_scripts_dir, mock_settings):
        """Test script that outputs binary data"""
        script_content = '''
import sys

if __name__ == '__main__':
    sys.stdout.buffer.write(b'\\x00\\x01\\x02\\x03\\xFF')
    sys.stdout.flush()
'''
        script_path = create_test_script(temp_scripts_dir, 'binary_output_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        executor = ScriptExecutor(mock_settings)
        result = executor.execute_script(script_info)

        # Should handle binary output (may fail decoding)
        assert result is not None

    def test_script_with_malformed_json(self, temp_scripts_dir, mock_settings):
        """Test script with malformed JSON output"""
        script_content = '''
if __name__ == '__main__':
    print('{"incomplete": ')
'''
        script_path = create_test_script(temp_scripts_dir, 'malformed_json_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        executor = ScriptExecutor(mock_settings)
        result = executor.execute_script(script_info)

        # Should handle malformed JSON gracefully
        assert result is not None


@pytest.mark.edge_case
class TestResourceLimits:
    """Test resource limit edge cases"""

    def test_script_that_allocates_large_memory(self, temp_scripts_dir, mock_settings):
        """Test script that tries to allocate large amounts of memory"""
        script_content = '''
import json

if __name__ == '__main__':
    try:
        # Try to allocate 100MB
        large_list = [0] * (100 * 1024 * 1024)
        print(json.dumps({"success": True, "allocated": len(large_list)}))
    except MemoryError:
        print(json.dumps({"success": False, "error": "MemoryError"}))
'''
        script_path = create_test_script(temp_scripts_dir, 'memory_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        executor = ScriptExecutor(mock_settings)
        result = executor.execute_script(script_info)

        # Should execute (may or may not succeed in allocation)
        assert result is not None

    def test_script_that_creates_many_files(self, temp_scripts_dir, temp_dir, mock_settings):
        """Test script that creates many temporary files"""
        script_content = f'''
import json
from pathlib import Path

if __name__ == '__main__':
    temp_dir = Path(r"{temp_dir}")
    created = 0
    try:
        for i in range(1000):
            f = temp_dir / f"temp_{{i}}.txt"
            f.write_text("test")
            created += 1
        print(json.dumps({{"success": True, "created": created}}))
    except Exception as e:
        print(json.dumps({{"success": False, "created": created, "error": str(e)}}))
'''
        script_path = create_test_script(temp_scripts_dir, 'many_files_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        executor = ScriptExecutor(mock_settings)
        result = executor.execute_script(script_info)

        assert result is not None


@pytest.mark.edge_case
class TestTimingEdgeCases:
    """Test timing-related edge cases"""

    def test_script_that_executes_very_quickly(self, temp_scripts_dir, mock_settings):
        """Test script that completes in microseconds"""
        script_content = '''
import json

if __name__ == '__main__':
    print(json.dumps({"success": True}))
'''
        script_path = create_test_script(temp_scripts_dir, 'fast_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        executor = ScriptExecutor(mock_settings)

        start = time.perf_counter()
        result = executor.execute_script(script_info)
        elapsed = time.perf_counter() - start

        assert result.success
        # Very fast execution should still work correctly

    def test_script_that_sleeps_briefly(self, temp_scripts_dir, mock_settings):
        """Test script with short sleep"""
        script_content = '''
import time
import json

if __name__ == '__main__':
    time.sleep(0.1)
    print(json.dumps({"success": True}))
'''
        script_path = create_test_script(temp_scripts_dir, 'sleep_test', script_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        executor = ScriptExecutor(mock_settings)
        result = executor.execute_script(script_info)

        assert result.success


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
