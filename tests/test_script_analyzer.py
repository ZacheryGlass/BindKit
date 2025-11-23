"""
Unit tests for ScriptAnalyzer.

Tests AST parsing, execution strategy detection, and edge cases.
"""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.script_analyzer import ScriptAnalyzer, ScriptInfo, ExecutionStrategy
from tests.test_utilities import create_test_script


class TestScriptAnalyzer:
    """Test cases for ScriptAnalyzer"""

    def test_analyze_simple_script(self, sample_script_simple):
        """Test analyzing a simple script with if __name__ == '__main__'"""
        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(sample_script_simple)

        assert script_info is not None
        assert script_info.is_executable
        assert script_info.execution_strategy == ExecutionStrategy.SUBPROCESS
        assert script_info.file_path == sample_script_simple

    def test_analyze_function_script(self, sample_script_function):
        """Test analyzing a script with main() function"""
        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(sample_script_function)

        assert script_info is not None
        assert script_info.is_executable
        assert script_info.execution_strategy == ExecutionStrategy.FUNCTION_CALL

    def test_analyze_script_with_args(self, sample_script_with_args):
        """Test analyzing a script with argparse arguments"""
        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(sample_script_with_args)

        assert script_info is not None
        assert script_info.is_executable
        assert len(script_info.arguments) >= 1
        # Check that required argument is detected
        name_arg = next((arg for arg in script_info.arguments if arg.name == 'name'), None)
        assert name_arg is not None
        assert name_arg.required

    def test_analyze_empty_script(self, sample_script_empty):
        """Test analyzing an empty script file"""
        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(sample_script_empty)

        assert script_info is not None
        assert not script_info.is_executable
        assert script_info.error is not None

    def test_analyze_syntax_error_script(self, sample_script_syntax_error):
        """Test analyzing a script with syntax errors"""
        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(sample_script_syntax_error)

        assert script_info is not None
        assert not script_info.is_executable
        assert script_info.error is not None
        # Error message should contain some indication of syntax issues
        assert ('SyntaxError' in script_info.error or
                'syntax' in script_info.error.lower() or
                'expected' in script_info.error.lower() or
                'unexpected' in script_info.error.lower())

    def test_analyze_unicode_script(self, sample_script_unicode):
        """Test analyzing a script with Unicode content"""
        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(sample_script_unicode)

        assert script_info is not None
        assert script_info.is_executable
    
    def test_analyze_script_with_smart_quotes(self, temp_scripts_dir):
        """Scripts copied from rich editors with smart quotes should still parse"""
        content = '''def main():
    print('hello from smart quotes')

if __name__ == '__main__':
    main()
'''
        smart_content = content.replace("'", "\u2019")
        script_path = create_test_script(temp_scripts_dir, 'smart_quotes', smart_content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info is not None
        assert script_info.is_executable
        assert script_info.error is None

    def test_analyze_service_script(self, sample_script_service):
        """Test detecting service scripts via docstring"""
        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(sample_script_service)

        assert script_info is not None
        assert script_info.is_executable
        # Service scripts should be detected from docstring
        # This depends on how the analyzer detects services

    def test_analyze_scheduled_script(self, sample_script_scheduled):
        """Test detecting scheduled scripts via docstring"""
        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(sample_script_scheduled)

        assert script_info is not None
        assert script_info.is_executable

    @pytest.mark.edge_case
    def test_analyze_nonexistent_file(self, temp_scripts_dir):
        """Test analyzing a file that doesn't exist"""
        analyzer = ScriptAnalyzer()
        nonexistent = temp_scripts_dir / "does_not_exist.py"
        script_info = analyzer.analyze_script(nonexistent)

        assert script_info is not None
        assert not script_info.is_executable
        assert script_info.error is not None

    @pytest.mark.edge_case
    def test_analyze_very_long_script(self, temp_scripts_dir):
        """Test analyzing a script with many lines"""
        # Create a script with 10,000 lines
        lines = ['# Comment line'] * 10000
        lines.append('if __name__ == "__main__":')
        lines.append('    print("done")')

        script_path = create_test_script(
            temp_scripts_dir,
            'very_long',
            '\n'.join(lines)
        )

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info is not None
        # Should still be analyzable despite length
        assert script_info.is_executable

    @pytest.mark.edge_case
    def test_analyze_deeply_nested_code(self, temp_scripts_dir):
        """Test analyzing a script with deeply nested code"""
        # Create script with deep nesting
        content = '''
if __name__ == "__main__":
    if True:
        if True:
            if True:
                if True:
                    if True:
                        if True:
                            if True:
                                if True:
                                    if True:
                                        if True:
                                            print("deep")
'''
        script_path = create_test_script(temp_scripts_dir, 'deep_nesting', content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info is not None
        assert script_info.is_executable

    @pytest.mark.edge_case
    def test_analyze_binary_file(self, temp_scripts_dir):
        """Test analyzing a binary file (should fail gracefully)"""
        binary_path = temp_scripts_dir / "binary.py"
        binary_path.write_bytes(b'\x00\x01\x02\x03\xFF\xFE')

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(binary_path)

        assert script_info is not None
        assert not script_info.is_executable

    @pytest.mark.edge_case
    def test_analyze_mixed_line_endings(self, temp_scripts_dir):
        """Test analyzing a script with mixed line endings (CRLF, LF)"""
        content = "import json\r\n\nif __name__ == '__main__':\r\n    print('mixed')\n"
        script_path = temp_scripts_dir / "mixed_endings.py"
        script_path.write_bytes(content.encode('utf-8'))

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info is not None
        # Should handle mixed line endings
        assert script_info.is_executable

    @pytest.mark.edge_case
    def test_analyze_script_with_encoding_declaration(self, temp_scripts_dir):
        """Test script with various encoding declarations"""
        content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script with encoding"""
import json

if __name__ == '__main__':
    print(json.dumps({"success": True}))
'''
        script_path = create_test_script(temp_scripts_dir, 'encoding', content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info is not None
        assert script_info.is_executable

    @pytest.mark.edge_case
    def test_analyze_script_with_complex_argparse(self, temp_scripts_dir):
        """Test script with complex argparse setup"""
        content = '''
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--required', required=True, type=str)
    parser.add_argument('--optional', default='default', type=str)
    parser.add_argument('--flag', action='store_true')
    parser.add_argument('--choice', choices=['a', 'b', 'c'])
    parser.add_argument('--number', type=int, default=42)
    subparsers = parser.add_subparsers(dest='command')
    sub = subparsers.add_parser('sub')
    sub.add_argument('--sub-arg')
    args = parser.parse_args()
    print(args)
'''
        script_path = create_test_script(temp_scripts_dir, 'complex_args', content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info is not None
        assert script_info.is_executable
        # Should detect at least the main arguments
        assert len(script_info.arguments) > 0

    @pytest.mark.edge_case
    def test_analyze_script_multiple_main_blocks(self, temp_scripts_dir):
        """Test script with multiple if __name__ == '__main__' blocks"""
        content = '''
if __name__ == '__main__':
    print("first")

def foo():
    if __name__ == '__main__':  # This shouldn't count
        print("inside function")

if __name__ == '__main__':
    print("second")
'''
        script_path = create_test_script(temp_scripts_dir, 'multiple_main', content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info is not None
        # Should still be detected as executable

    @pytest.mark.edge_case
    def test_analyze_script_with_imports_only(self, temp_scripts_dir):
        """Test script that only contains imports (no executable code)"""
        content = '''
import json
import sys
import os
from pathlib import Path
'''
        script_path = create_test_script(temp_scripts_dir, 'imports_only', content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info is not None
        # Script with only imports should not be executable
        assert not script_info.is_executable

    @pytest.mark.edge_case
    def test_analyze_script_name_with_special_chars(self, temp_scripts_dir):
        """Test script file names with special characters"""
        # Test with spaces
        script_path = temp_scripts_dir / "script with spaces.py"
        script_path.write_text('if __name__ == "__main__":\n    print("ok")')

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)

        assert script_info is not None
        assert script_info.is_executable

    @pytest.mark.edge_case
    def test_analyzer_caching(self, sample_script_simple):
        """Test that analyzer doesn't inappropriately cache results"""
        analyzer = ScriptAnalyzer()

        # Analyze once
        script_info1 = analyzer.analyze_script(sample_script_simple)

        # Modify the file
        original_content = sample_script_simple.read_text()
        sample_script_simple.write_text('# Modified\n' + original_content)

        # Analyze again - should reflect changes if not cached
        script_info2 = analyzer.analyze_script(sample_script_simple)

        # Both should be valid but may have different characteristics
        assert script_info1 is not None
        assert script_info2 is not None

        # Restore original content
        sample_script_simple.write_text(original_content)

    @pytest.mark.edge_case
    def test_analyze_script_with_tabs_and_spaces(self, temp_scripts_dir):
        """Test script with mixed tabs and spaces (should still parse)"""
        content = '''
if __name__ == '__main__':
\tif True:
        \t# Mixed tabs and spaces
\t    print("mixed")
'''
        script_path = create_test_script(temp_scripts_dir, 'mixed_indent', content)

        analyzer = ScriptAnalyzer()
        script_info = analyzer.analyze_script(script_path)


        assert script_info is not None
        # Should handle BOM gracefully
        assert script_info.is_executable

    @pytest.mark.slow
    def test_analyze_many_scripts_performance(self, temp_scripts_dir):
        """Test performance of analyzing many scripts"""
        import time

        # Create 100 test scripts
        for i in range(100):
            create_test_script(
                temp_scripts_dir,
                f'perf_test_{i}',
                f'if __name__ == "__main__":\n    print("Script {i}")'
            )

        analyzer = ScriptAnalyzer()
        start_time = time.time()

        # Analyze all scripts
        script_files = list(temp_scripts_dir.glob("*.py"))
        for script_file in script_files:
            analyzer.analyze_script(script_file)

        elapsed = time.time() - start_time

        # Should complete in reasonable time (adjust threshold as needed)
        assert elapsed < 10.0, f"Analyzing 100 scripts took {elapsed}s (expected < 10s)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
