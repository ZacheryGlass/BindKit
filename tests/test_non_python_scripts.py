"""
Tests for PowerShell, Batch, and Shell script support.
"""

import pytest
from pathlib import Path
import tempfile
import os
from core.script_analyzer import ScriptAnalyzer, ScriptType, ExecutionStrategy, ArgumentInfo
from core.script_executor import ScriptExecutor
from core.settings import SettingsManager


class TestPowerShellAnalyzer:
    """Test PowerShell script analysis."""

    def test_analyze_simple_powershell_script(self):
        """Test analyzing a simple PowerShell script."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False) as f:
            f.write("Write-Host 'Hello World'\n")
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.POWERSHELL
                assert result.execution_strategy == ExecutionStrategy.POWERSHELL
                assert result.is_executable
                assert not result.error

            finally:
                os.unlink(f.name)

    def test_analyze_powershell_with_params(self):
        """Test analyzing PowerShell script with parameters."""
        ps_code = """
param(
    [Parameter(Mandatory=$true)]
    [string]$Name,

    [Parameter(Mandatory=$false)]
    [string]$Message = "Hello"
)

Write-Host "$Message, $Name"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False) as f:
            f.write(ps_code)
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.POWERSHELL
                assert len(result.arguments) >= 1
                # At least Name parameter should be found
                assert any(arg.name == 'Name' for arg in result.arguments)

            finally:
                os.unlink(f.name)

    def test_empty_powershell_script(self):
        """Test analyzing empty PowerShell script."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False) as f:
            f.write("")
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.POWERSHELL
                assert not result.is_executable
                assert result.error

            finally:
                os.unlink(f.name)


class TestBatchAnalyzer:
    """Test Batch script analysis."""

    def test_analyze_simple_batch_script(self):
        """Test analyzing a simple Batch script."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False) as f:
            f.write("@echo off\necho Hello World\n")
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.BATCH
                assert result.execution_strategy == ExecutionStrategy.BATCH
                assert result.is_executable
                assert not result.error

            finally:
                os.unlink(f.name)

    def test_analyze_batch_with_args(self):
        """Test analyzing Batch script with parameters."""
        batch_code = """@echo off
REM %1 - First parameter
REM %2 - Second parameter
echo Arg 1: %1
echo Arg 2: %2
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False) as f:
            f.write(batch_code)
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.BATCH
                assert len(result.arguments) >= 2
                # Should find arg1 and arg2
                assert any(arg.name == 'arg1' for arg in result.arguments)
                assert any(arg.name == 'arg2' for arg in result.arguments)

            finally:
                os.unlink(f.name)

    def test_cmd_extension(self):
        """Test analyzing .cmd file (should be treated as batch)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cmd', delete=False) as f:
            f.write("@echo off\necho Test\n")
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.BATCH
                assert result.execution_strategy == ExecutionStrategy.BATCH

            finally:
                os.unlink(f.name)

    def test_empty_batch_script(self):
        """Test analyzing empty Batch script."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False) as f:
            f.write("")
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.BATCH
                assert not result.is_executable

            finally:
                os.unlink(f.name)


class TestShellAnalyzer:
    """Test Shell script analysis."""

    def test_analyze_simple_shell_script(self):
        """Test analyzing a simple shell script."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("#!/bin/bash\necho 'Hello World'\n")
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.SHELL
                assert result.execution_strategy == ExecutionStrategy.SHELL
                assert result.is_executable
                assert not result.error

            finally:
                os.unlink(f.name)

    def test_analyze_shell_with_getopts(self):
        """Test analyzing shell script with getopts."""
        shell_code = """#!/bin/bash
while getopts "a:b:c" opt; do
    case $opt in
        a) ARG_A="$OPTARG" ;;  # First argument
        b) ARG_B="$OPTARG" ;;  # Second argument
        c) ARG_C=1 ;;          # Flag
    esac
done
echo "A=$ARG_A B=$ARG_B C=$ARG_C"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(shell_code)
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.SHELL
                assert len(result.arguments) >= 1
                # Should find getopts options
                assert any(arg.name in ['a', 'b', 'c'] for arg in result.arguments)

            finally:
                os.unlink(f.name)

    def test_analyze_shell_with_positional_args(self):
        """Test analyzing shell script with positional arguments."""
        shell_code = """#!/bin/bash
# $1 - First parameter
# $2 - Second parameter
echo "Arg 1: $1"
echo "Arg 2: $2"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write(shell_code)
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.SHELL
                assert len(result.arguments) >= 2

            finally:
                os.unlink(f.name)

    def test_empty_shell_script(self):
        """Test analyzing empty shell script."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("#!/bin/bash\n")
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.SHELL
                assert not result.is_executable

            finally:
                os.unlink(f.name)


class TestScriptTypeRouting:
    """Test that analyze_script routes to correct type analyzer."""

    def test_python_routing(self):
        """Test .py files route to Python analyzer."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write("print('hello')\n")
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.PYTHON

            finally:
                os.unlink(f.name)

    def test_powershell_routing(self):
        """Test .ps1 files route to PowerShell analyzer."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False) as f:
            f.write("Write-Host 'test'\n")
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.POWERSHELL

            finally:
                os.unlink(f.name)

    def test_batch_routing(self):
        """Test .bat files route to Batch analyzer."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False) as f:
            f.write("echo test\n")
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.BATCH

            finally:
                os.unlink(f.name)

    def test_shell_routing(self):
        """Test .sh files route to Shell analyzer."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("echo test\n")
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert result.script_type == ScriptType.SHELL

            finally:
                os.unlink(f.name)

    def test_unsupported_extension(self):
        """Test unsupported file extensions."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("test content\n")
            f.flush()

            try:
                analyzer = ScriptAnalyzer()
                result = analyzer.analyze_script(Path(f.name))

                assert not result.is_executable
                assert result.error
                assert "Unsupported" in result.error

            finally:
                os.unlink(f.name)


class TestSettingsForMultipleScriptTypes:
    """Test settings support for multiple script types."""

    def test_external_script_validation_multiple_types(self):
        """Test that external scripts can be .py, .ps1, .bat, or .sh files."""
        settings = SettingsManager()

        # Create temporary script files of each type
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test .py
            py_path = Path(tmpdir) / "test.py"
            py_path.write_text("print('test')")
            assert settings.validate_external_script_path(str(py_path))

            # Test .ps1
            ps_path = Path(tmpdir) / "test.ps1"
            ps_path.write_text("Write-Host 'test'")
            assert settings.validate_external_script_path(str(ps_path))

            # Test .bat
            bat_path = Path(tmpdir) / "test.bat"
            bat_path.write_text("echo test")
            assert settings.validate_external_script_path(str(bat_path))

            # Test .sh
            sh_path = Path(tmpdir) / "test.sh"
            sh_path.write_text("echo test")
            assert settings.validate_external_script_path(str(sh_path))

    def test_interpreter_settings(self):
        """Test interpreter path settings."""
        settings = SettingsManager()

        # Reset to defaults first
        settings.set('interpreters/wsl_distro', 'Ubuntu')
        settings.sync()

        # Test getting default interpreter settings
        ps_path = settings.get('interpreters/powershell_path')
        bash_path = settings.get('interpreters/bash_path')
        wsl_distro = settings.get('interpreters/wsl_distro')
        use_wsl = settings.get('interpreters/use_wsl')

        assert wsl_distro == 'Ubuntu'
        assert use_wsl is True

        # Test setting custom paths
        settings.set('interpreters/powershell_path', '/custom/pwsh')
        assert settings.get('interpreters/powershell_path') == '/custom/pwsh'

        settings.set('interpreters/wsl_distro', 'Debian')
        assert settings.get('interpreters/wsl_distro') == 'Debian'

        # Clean up - reset to defaults for next test run
        settings.set('interpreters/wsl_distro', 'Ubuntu')
        settings.set('interpreters/powershell_path', None)
        settings.sync()
