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

class ExecutionStrategy(Enum):
    SUBPROCESS = "subprocess"
    FUNCTION_CALL = "function_call"
    MODULE_EXEC = "module_exec"
    SERVICE = "service"

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
        """Analyze a Python script to determine how to execute it and what arguments it needs."""
        logger.debug(f"Analyzing script: {script_path}")
        
        display_name = self._get_display_name(script_path)
        
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            
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

            return ScriptInfo(
                file_path=script_path,
                display_name=display_name,
                execution_strategy=execution_strategy,
                main_function='main' if has_main_function else None,
                arguments=arguments,
                has_main_block=has_main_block,
                is_executable=True,
                needs_configuration=needs_configuration
            )
            
        except Exception as e:
            logger.error(f"Error analyzing script {script_path}: {str(e)}")
            return ScriptInfo(
                file_path=script_path,
                display_name=display_name,
                execution_strategy=ExecutionStrategy.SUBPROCESS,
                is_executable=False,
                error=str(e)
            )
    
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