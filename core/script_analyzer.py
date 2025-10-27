import ast
import os
import sys
import importlib.util
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('Core.ScriptAnalyzer')

SMART_PUNCTUATION_TRANSLATIONS = {
    '\u2018': "'",  # left single quote
    '\u2019': "'",  # right single quote
    '\u201a': "'",  # single low-9
    '\u201b': "'",  # single high-reversed-9
    '\u201c': '"',  # left double quote
    '\u201d': '"',  # right double quote
    '\u201e': '"',  # double low-9
    '\u201f': '"',  # double high-reversed-9
    '\u00ab': '"',  # left-pointing double angle
    '\u00bb': '"',  # right-pointing double angle
    '\u2013': '-',  # en dash
    '\u2014': '-',  # em dash
    '\u2015': '-',  # horizontal bar
    '\u2212': '-',  # minus sign
    '\u00a0': ' ',  # non-breaking space
}
SMART_PUNCTUATION_TABLE = str.maketrans(SMART_PUNCTUATION_TRANSLATIONS)
SMART_PUNCTUATION_CHARS = set(SMART_PUNCTUATION_TRANSLATIONS.keys())

class ScriptType(Enum):
    PYTHON = "python"
    POWERSHELL = "powershell"
    BATCH = "batch"
    SHELL = "shell"

class ExecutionStrategy(Enum):
    SUBPROCESS = "subprocess"
    FUNCTION_CALL = "function_call"
    MODULE_EXEC = "module_exec"
    SERVICE = "service"
    POWERSHELL = "powershell"
    BATCH = "batch"
    SHELL = "shell"

@dataclass
class ArgumentInfo:
    name: str
    required: bool = False
    default: Any = None
    help: str = ""
    type: str = "str"
    choices: Optional[List[str]] = None

@dataclass
class ScriptInfo:
    file_path: Path
    display_name: str
    execution_strategy: ExecutionStrategy
    script_type: ScriptType = ScriptType.PYTHON
    interpreter_path: Optional[str] = None
    main_function: Optional[str] = None
    arguments: List[ArgumentInfo] = None
    has_main_block: bool = False
    is_executable: bool = False
    error: Optional[str] = None
    needs_configuration: bool = False

    def __post_init__(self):
        if self.arguments is None:
            self.arguments = []

class ScriptAnalyzer:
    def __init__(self, settings=None):
        self.settings = settings
    
    def analyze_script(self, script_path: Path) -> ScriptInfo:
        """Analyze a script to determine how to execute it and what arguments it needs."""
        logger.debug(f"Analyzing script: {script_path}")

        # Route to appropriate analyzer based on file extension
        suffix = script_path.suffix.lower()

        if suffix == '.py':
            return self._analyze_python_script(script_path)
        elif suffix == '.ps1':
            return self._analyze_powershell_script(script_path)
        elif suffix in ['.bat', '.cmd']:
            return self._analyze_batch_script(script_path)
        elif suffix == '.sh':
            return self._analyze_shell_script(script_path)
        else:
            display_name = self._get_display_name(script_path)
            return ScriptInfo(
                file_path=script_path,
                display_name=display_name,
                execution_strategy=ExecutionStrategy.SUBPROCESS,
                is_executable=False,
                error=f"Unsupported script type: {suffix}"
            )

    def _analyze_python_script(self, script_path: Path) -> ScriptInfo:
        """Analyze a Python script to determine how to execute it and what arguments it needs."""
        logger.debug(f"Analyzing Python script: {script_path}")

        display_name = self._get_display_name(script_path)

        try:
            with open(script_path, 'r', encoding='utf-8-sig') as f:
                source_code = f.read()
            
            # Normalize any problematic smart punctuation so the parser sees ASCII
            source_code = self._sanitize_source_text(source_code, script_path)
            
            # Parse the AST
            tree = ast.parse(source_code)
            
            # Analyze the script structure
            has_main_function = self._has_main_function(tree)
            has_main_block = self._has_main_block(source_code)
            arguments = self._extract_arguments(tree, source_code)
            
            # Determine execution strategy
            execution_strategy = self._determine_execution_strategy(has_main_function, has_main_block, arguments)

            # Check if script is configured as a service (overrides normal execution strategy)
            script_name = script_path.stem
            if self.settings and self.settings.is_script_service(script_name):
                execution_strategy = ExecutionStrategy.SERVICE
                logger.info(f"Script '{script_name}' is configured as a service")

            # Determine if script needs configuration
            needs_configuration = self._determine_configuration_needs(arguments)

            # Determine if script is actually executable (has executable code)
            is_executable = has_main_block or has_main_function
            error_message = None
            if not is_executable:
                # Check if script has any code beyond imports
                has_code = self._has_executable_code(tree)
                is_executable = has_code
                if not is_executable:
                    if not source_code.strip():
                        error_message = "Script is empty"
                    else:
                        error_message = "Script has no executable code"

            return ScriptInfo(
                file_path=script_path,
                display_name=display_name,
                execution_strategy=execution_strategy,
                script_type=ScriptType.PYTHON,
                main_function='main' if has_main_function else None,
                arguments=arguments,
                has_main_block=has_main_block,
                is_executable=is_executable,
                needs_configuration=needs_configuration,
                error=error_message
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Python script {script_path}: {str(e)}")
            return ScriptInfo(
                file_path=script_path,
                display_name=display_name,
                execution_strategy=ExecutionStrategy.SUBPROCESS,
                script_type=ScriptType.PYTHON,
                is_executable=False,
                error=str(e)
            )
    
    def _analyze_powershell_script(self, script_path: Path) -> ScriptInfo:
        """Analyze a PowerShell script to extract parameters and metadata."""
        logger.debug(f"Analyzing PowerShell script: {script_path}")

        display_name = self._get_display_name(script_path)

        try:
            with open(script_path, 'r', encoding='utf-8-sig') as f:
                source_code = f.read()

            # Extract arguments from param() block
            arguments = self._extract_powershell_params(source_code)

            # PowerShell scripts are always executable if they have content
            is_executable = bool(source_code.strip())

            return ScriptInfo(
                file_path=script_path,
                display_name=display_name,
                execution_strategy=ExecutionStrategy.POWERSHELL,
                script_type=ScriptType.POWERSHELL,
                arguments=arguments,
                is_executable=is_executable,
                needs_configuration=any(arg.required for arg in arguments),
                error=None if is_executable else "Script is empty"
            )

        except Exception as e:
            logger.error(f"Error analyzing PowerShell script {script_path}: {str(e)}")
            return ScriptInfo(
                file_path=script_path,
                display_name=display_name,
                execution_strategy=ExecutionStrategy.POWERSHELL,
                script_type=ScriptType.POWERSHELL,
                is_executable=False,
                error=str(e)
            )

    def _extract_powershell_params(self, source_code: str) -> List[ArgumentInfo]:
        """Extract parameter information from PowerShell param() block."""
        import re

        arguments = []

        # Find param() block - supports multiline and nested parentheses
        # We need to match nested parens in [Parameter(...)]
        # Use a more sophisticated approach: find "param(" then match until we find the closing ")"
        param_start = re.search(r'param\s*\(', source_code, re.IGNORECASE)
        if not param_start:
            logger.debug("No param() block found in PowerShell script")
            return arguments

        # Find the matching closing parenthesis
        paren_count = 1
        start_pos = param_start.end()
        pos = start_pos

        while pos < len(source_code) and paren_count > 0:
            if source_code[pos] == '(':
                paren_count += 1
            elif source_code[pos] == ')':
                paren_count -= 1
            pos += 1

        if paren_count != 0:
            logger.debug("No matching closing parenthesis found in PowerShell script")
            return arguments

        param_block = source_code[start_pos:pos - 1]

        # Extract individual parameters
        # Pattern to match PowerShell parameter declarations with flexible whitespace/newlines
        # Matches patterns like:
        #   [Parameter(Mandatory=$true)]
        #   [string]$Name
        # or
        #   [Parameter(Mandatory=$false)]
        #   [string]$Message = "default"

        # First, find all lines that have a $variable declaration
        var_pattern = r'\$(\w+)'

        # For each parameter found, check if it has a [Parameter()] decorator
        for var_match in re.finditer(var_pattern, param_block):
            param_name = var_match.group(1)
            var_start = var_match.start()

            # Look backward from the variable to find decorators
            # Get text from start of param_block to the variable
            leading_text = param_block[:var_start]

            # Check if this parameter was already processed (it will be at the end of leading_text)
            last_newline = leading_text.rfind('\n')
            if last_newline == -1:
                last_newline = 0
            else:
                last_newline += 1

            line_before_var = leading_text[last_newline:]

            # Check for [Parameter(...)] in recent lines before this variable
            param_decorator_pattern = r'\[Parameter\([^\]]*Mandatory=\$true[^\]]*\)\]'
            is_mandatory = bool(re.search(param_decorator_pattern, leading_text[-200:], re.IGNORECASE))

            # Look for type annotation [Type]$Name
            type_pattern = r'\[(\w+)\]\s*\$' + re.escape(param_name)
            type_match = re.search(type_pattern, param_block)
            param_type = type_match.group(1).lower() if type_match else 'string'

            # Try to extract help message from comment on the same line or nearby
            help_text = ""
            help_pattern = rf'\${{param_name}}\s*(?:=\s*[^\n]*)?\s*#\s*(.+?)(?:\n|$)'
            help_match = re.search(help_pattern, param_block)
            if help_match:
                help_text = help_match.group(1).strip()

            # Only add if we found a type annotation or Parameter attribute (to filter out $0, $1, etc.)
            if re.search(r'\[' + re.escape(param_type) + r'\]\s*\$' + re.escape(param_name), param_block):
                arguments.append(ArgumentInfo(
                    name=param_name,
                    required=is_mandatory,
                    type=param_type,
                    help=help_text
                ))

        logger.debug(f"Extracted {len(arguments)} PowerShell parameters")
        return arguments

    def _analyze_batch_script(self, script_path: Path) -> ScriptInfo:
        """Analyze a Batch script (.bat or .cmd file)."""
        logger.debug(f"Analyzing Batch script: {script_path}")

        display_name = self._get_display_name(script_path)

        try:
            with open(script_path, 'r', encoding='utf-8-sig') as f:
                source_code = f.read()

            # Extract arguments from %1, %2, etc. usage
            arguments = self._extract_batch_params(source_code)

            # Batch scripts are always executable if they have content (not just comments)
            # Remove empty lines and comments to check for actual code
            code_lines = [line.strip() for line in source_code.split('\n')
                         if line.strip() and not line.strip().startswith('REM')
                         and not line.strip().startswith('::')]
            is_executable = bool(code_lines)

            return ScriptInfo(
                file_path=script_path,
                display_name=display_name,
                execution_strategy=ExecutionStrategy.BATCH,
                script_type=ScriptType.BATCH,
                arguments=arguments,
                is_executable=is_executable,
                needs_configuration=any(arg.required for arg in arguments),
                error=None if is_executable else "Script is empty or contains only comments"
            )

        except Exception as e:
            logger.error(f"Error analyzing Batch script {script_path}: {str(e)}")
            return ScriptInfo(
                file_path=script_path,
                display_name=display_name,
                execution_strategy=ExecutionStrategy.BATCH,
                script_type=ScriptType.BATCH,
                is_executable=False,
                error=str(e)
            )

    def _extract_batch_params(self, source_code: str) -> List[ArgumentInfo]:
        """Extract parameter information from Batch script usage."""
        import re

        arguments = []

        # Find usage of %1, %2, etc.
        param_pattern = r'%(\d+)'
        param_numbers = set()

        for match in re.finditer(param_pattern, source_code):
            param_num = int(match.group(1))
            if param_num > 0 and param_num <= 9:  # Batch supports %1-%9
                param_numbers.add(param_num)

        # Create arguments for each found parameter
        for param_num in sorted(param_numbers):
            # Try to find description in REM comments
            help_text = ""
            help_pattern = rf'REM.*?%{param_num}.*?-\s*(.+?)(?:\n|$)'
            help_match = re.search(help_pattern, source_code, re.IGNORECASE)
            if help_match:
                help_text = help_match.group(1).strip()

            arguments.append(ArgumentInfo(
                name=f"arg{param_num}",
                required=False,  # Batch doesn't have a concept of required params
                type="str",
                help=help_text
            ))

        logger.debug(f"Extracted {len(arguments)} Batch parameters")
        return arguments

    def _analyze_shell_script(self, script_path: Path) -> ScriptInfo:
        """Analyze a Shell script (.sh file)."""
        logger.debug(f"Analyzing Shell script: {script_path}")

        display_name = self._get_display_name(script_path)

        try:
            with open(script_path, 'r', encoding='utf-8-sig') as f:
                source_code = f.read()

            # Extract arguments from getopts or positional parameters
            arguments = self._extract_shell_params(source_code)

            # Shell scripts are executable if they have content (not just comments)
            code_lines = [line.strip() for line in source_code.split('\n')
                         if line.strip() and not line.strip().startswith('#')]
            is_executable = bool(code_lines)

            return ScriptInfo(
                file_path=script_path,
                display_name=display_name,
                execution_strategy=ExecutionStrategy.SHELL,
                script_type=ScriptType.SHELL,
                arguments=arguments,
                is_executable=is_executable,
                needs_configuration=any(arg.required for arg in arguments),
                error=None if is_executable else "Script is empty or contains only comments"
            )

        except Exception as e:
            logger.error(f"Error analyzing Shell script {script_path}: {str(e)}")
            return ScriptInfo(
                file_path=script_path,
                display_name=display_name,
                execution_strategy=ExecutionStrategy.SHELL,
                script_type=ScriptType.SHELL,
                is_executable=False,
                error=str(e)
            )

    def _extract_shell_params(self, source_code: str) -> List[ArgumentInfo]:
        """Extract parameter information from Shell script."""
        import re

        arguments = []

        # First, try to find getopts usage
        # Example: while getopts "a:b:c" opt; do
        getopts_pattern = r'getopts\s+"([^"]+)"'
        getopts_match = re.search(getopts_pattern, source_code)

        if getopts_match:
            # Parse getopts string
            getopts_str = getopts_match.group(1)
            i = 0
            while i < len(getopts_str):
                if getopts_str[i].isalpha():
                    opt_name = getopts_str[i]
                    # Check if it requires an argument (followed by :)
                    requires_arg = (i + 1 < len(getopts_str) and getopts_str[i + 1] == ':')

                    # Try to find help text in comments near the case statement
                    help_text = ""
                    help_pattern = rf'{opt_name}\)\s*#\s*(.+?)(?:\n|$)'
                    help_match = re.search(help_pattern, source_code)
                    if help_match:
                        help_text = help_match.group(1).strip()

                    arguments.append(ArgumentInfo(
                        name=opt_name,
                        required=False,  # getopts options are typically optional
                        type="str",
                        help=help_text
                    ))

                i += 1

        else:
            # Check for positional parameters $1, $2, etc.
            param_pattern = r'\$(\d+)'
            param_numbers = set()

            for match in re.finditer(param_pattern, source_code):
                param_num = int(match.group(1))
                if param_num > 0 and param_num <= 9:
                    param_numbers.add(param_num)

            # Create arguments for each found parameter
            for param_num in sorted(param_numbers):
                # Try to find description in comments
                help_text = ""
                help_pattern = rf'#.*?\${param_num}.*?-\s*(.+?)(?:\n|$)'
                help_match = re.search(help_pattern, source_code)
                if help_match:
                    help_text = help_match.group(1).strip()

                arguments.append(ArgumentInfo(
                    name=f"arg{param_num}",
                    required=False,
                    type="str",
                    help=help_text
                ))

        logger.debug(f"Extracted {len(arguments)} Shell parameters")
        return arguments

    def _sanitize_source_text(self, source_code: str, script_path: Path) -> str:
        """
        Replace smart quotes, non-breaking spaces, and similar characters with
        ASCII equivalents so scripts copied from rich-text editors still parse.
        """
        if not any(ch in SMART_PUNCTUATION_CHARS for ch in source_code):
            return source_code
        
        normalized = source_code.translate(SMART_PUNCTUATION_TABLE)
        logger.info(
            f"Normalized smart punctuation in {script_path.name} to avoid parse errors"
        )
        return normalized
    
    def _get_display_name(self, script_path: Path) -> str:
        """Get display name from filename."""
        name = script_path.stem
        # Convert snake_case or kebab-case to Title Case
        name = name.replace('_', ' ').replace('-', ' ')
        return ' '.join(word.capitalize() for word in name.split())
    
    def _has_main_function(self, tree: ast.AST) -> bool:
        """Check if the script has a main() function."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'main':
                return True
        return False
    
    def _has_main_block(self, source_code: str) -> bool:
        """Check if the script has if __name__ == "__main__": block."""
        return 'if __name__ == "__main__"' in source_code or "if __name__ == '__main__'" in source_code
    
    def _extract_arguments(self, tree: ast.AST, source_code: str) -> List[ArgumentInfo]:
        """Extract argument information from the script."""
        arguments = []
        
        # Look for argparse usage
        argparse_args = self._extract_argparse_arguments(tree)
        if argparse_args:
            arguments.extend(argparse_args)
        
        # If no argparse found, check main function signature
        if not arguments:
            main_args = self._extract_main_function_arguments(tree)
            if main_args:
                arguments.extend(main_args)
        
        logger.debug(f"Extracted {len(arguments)} arguments: {[arg.name for arg in arguments]}")
        return arguments
    
    def _extract_argparse_arguments(self, tree: ast.AST) -> List[ArgumentInfo]:
        """Extract arguments from argparse usage."""
        arguments = []
        
        # Look for ArgumentParser usage
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Look for add_argument calls
                if (isinstance(node.func, ast.Attribute) and 
                    node.func.attr == 'add_argument'):
                    
                    arg_info = self._parse_add_argument_call(node)
                    if arg_info:
                        arguments.append(arg_info)
        
        return arguments
    
    def _parse_add_argument_call(self, node: ast.Call) -> Optional[ArgumentInfo]:
        """Parse an add_argument call to extract argument information."""
        try:
            # First positional argument is the argument name
            if not node.args:
                return None
            
            arg_name = None
            if isinstance(node.args[0], ast.Str):
                arg_name = node.args[0].s
            elif isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                arg_name = node.args[0].value
            
            if not arg_name:
                return None
            
            # Remove -- prefix if present
            clean_name = arg_name.lstrip('-')
            
            # Parse keyword arguments
            required = False
            default = None
            help_text = ""
            arg_type = "str"
            choices = None
            
            for keyword in node.keywords:
                if keyword.arg == 'required':
                    if isinstance(keyword.value, ast.Constant):
                        required = keyword.value.value
                elif keyword.arg == 'default':
                    if isinstance(keyword.value, ast.Constant):
                        default = keyword.value.value
                elif keyword.arg == 'help':
                    if isinstance(keyword.value, ast.Str):
                        help_text = keyword.value.s
                    elif isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                        help_text = keyword.value.value
                elif keyword.arg == 'type':
                    if isinstance(keyword.value, ast.Name):
                        arg_type = keyword.value.id
                elif keyword.arg == 'choices':
                    if isinstance(keyword.value, ast.List):
                        choices = []
                        for item in keyword.value.elts:
                            if isinstance(item, ast.Str):
                                choices.append(item.s)
                            elif isinstance(item, ast.Constant):
                                choices.append(str(item.value))
            
            return ArgumentInfo(
                name=clean_name,
                required=required,
                default=default,
                help=help_text,
                type=arg_type,
                choices=choices
            )
            
        except Exception as e:
            logger.debug(f"Error parsing add_argument call: {e}")
            return None
    
    def _extract_main_function_arguments(self, tree: ast.AST) -> List[ArgumentInfo]:
        """Extract arguments from main function signature."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'main':
                arguments = []
                for arg in node.args.args:
                    # Skip 'self' parameter
                    if arg.arg == 'self':
                        continue
                    
                    arguments.append(ArgumentInfo(
                        name=arg.arg,
                        required=True,  # Function arguments are generally required
                        type="str"
                    ))
                
                return arguments
        
        return []
    
    def _determine_execution_strategy(self, has_main_function: bool, has_main_block: bool, arguments: List[ArgumentInfo]) -> ExecutionStrategy:
        """Determine the best execution strategy for the script."""

        # If script has arguments, prefer subprocess execution for easier argument passing
        if arguments:
            return ExecutionStrategy.SUBPROCESS

        # If has main function, prefer function call
        if has_main_function:
            return ExecutionStrategy.FUNCTION_CALL

        # If has main block, use subprocess
        if has_main_block:
            return ExecutionStrategy.SUBPROCESS

        # Default to module execution
        return ExecutionStrategy.MODULE_EXEC

    def _has_executable_code(self, tree: ast.AST) -> bool:
        """Check if script has any executable code beyond imports."""
        for node in ast.walk(tree):
            # Ignore imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                continue

            # Ignore module-level docstrings (string expressions at module level)
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                if isinstance(node.value.value, str):
                    continue

            # Look for actual executable statements
            if isinstance(node, (ast.Assign, ast.FunctionDef, ast.ClassDef,
                               ast.For, ast.While, ast.If, ast.With, ast.Try,
                               ast.Expr, ast.Call)):
                # For Expr nodes, check if it's not just a docstring
                if isinstance(node, ast.Expr):
                    if not isinstance(node.value, ast.Constant):
                        return True
                    if not isinstance(node.value.value, str):
                        return True
                else:
                    return True

        return False

    def _determine_configuration_needs(self, arguments: List[ArgumentInfo]) -> bool:
        """Determine if a script needs user configuration based on its arguments."""
        if not arguments:
            return False
        
        # Script needs configuration if it has any required arguments
        # or arguments without default values
        for arg in arguments:
            if arg.required or arg.default is None:
                return True
        
        return False
    
    def test_script_execution(self, script_info: ScriptInfo) -> bool:
        """Test if a script can be executed successfully."""
        try:
            if script_info.execution_strategy == ExecutionStrategy.SUBPROCESS:
                # Try running the script with --help to see if it works
                result = subprocess.run(
                    [sys.executable, str(script_info.file_path), '--help'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                # Script is valid if it runs (even if --help fails, it means the script loaded)
                return True
            else:
                # Try importing the module
                spec = importlib.util.spec_from_file_location("test_module", script_info.file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    return True
                
        except Exception as e:
            logger.debug(f"Script execution test failed for {script_info.file_path}: {e}")
        
        return False
