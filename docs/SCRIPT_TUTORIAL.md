# BindKit Script Tutorial

BindKit no longer ships a custom base class. Every script is a regular Python file that prints a JSON payload when it finishes. This guide walks through building reliable standalone scripts that work with hotkeys, schedules, and the tray UI.

## Prerequisites
- Windows with Python 3.10+
- Familiarity with argparse and standard library modules
- Ability to run/install external tools required by your script

## Lifecycle overview
1. Place a `.py` file inside `scripts/`
2. BindKit discovers it automatically on startup (or when you click Refresh)
3. The AST analyzer inspects the file:
   - Finds a `main()` function or `if __name__ == "__main__"` guard
   - Reads argparse metadata to build UI inputs
4. Script appears in the tray menu, Hotkeys tab, and Schedule tab
5. When triggered, BindKit executes the script using the best strategy and displays the JSON result

## Minimal CLI script
```python
#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description="Toggle the mute state")
    parser.add_argument("--device", default="Speakers", help="Audio endpoint name")
    args = parser.parse_args()

    try:
        subprocess.run([
            "nircmd.exe", "mutesysvolume", "2", args.device
        ], check=True)
        result = {"success": True, "message": f"Toggled {args.device}"}
    except subprocess.CalledProcessError as exc:
        result = {
            "success": False,
            "message": "Failed to toggle audio",
            "error": exc.stderr or str(exc),
        }

    print(json.dumps(result))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
```

### Why this works
- `argparse` is used (auto-detected by the analyzer)
- The script prints exactly one JSON object
- Exit code reflects success/failure

## Function-call scripts
For lightweight utilities that do not need CLI arguments you can expose a `main()` function without argparse. The executor will import the module once and reuse it.

```python
import json


def main():
    # Expensive initialization happens only once
    temperature_c = read_attached_sensor()
    return {
        "success": True,
        "message": f"Sensor temperature: {temperature_c:.1f}C",
        "data": {"temperature_c": temperature_c}
    }
```
BindKit handles conversion to JSON and return codes automatically for `FUNCTION_CALL` strategies.

## JSON contract
- `success` (bool) and `message` (str) are required
- Optional fields: `data` (dict/list), `output` (str), `error` (str)
- Avoid printing anything else to stdout; use stderr for debugging text if necessary

Example failure payload:
```python
print(json.dumps({
    "success": False,
    "message": "VPN client not installed",
    "error": "OpenVPN executable missing"
}))
sys.exit(1)
```

## Argument detection tips
- Prefer named `--flags` with `choices` to produce dropdowns automatically
- Use `required=True` for parameters that must be filled in through the Settings dialog
- Provide helpful `help` strings; they appear as tooltips
- Keep argument names snake_case; BindKit converts them to labels

## Services (long-running scripts)
Mark a script as a service in the Settings dialog to keep it running in the background. Service scripts should:
- Keep running until SIGTERM/CTRL_BREAK is received
- Log to stdout/stderr frequently so `logs/services/<script>.log` stays informative
- Handle restarts gracefully (the runtime may restart after crashes)

Simple example:
```python
#!/usr/bin/env python3
import json
import signal
import time

running = True


def handle_signal(*_):
    global running
    running = False


def main():
    signal.signal(signal.SIGTERM, handle_signal)
    while running:
        print(json.dumps({"success": True, "message": "Heartbeat"}))
        time.sleep(60)
```

## Scheduling-friendly practices
- Keep executions idempotent; schedules may run while a manual call is queued
- Respect the `arguments` persisted in settings; default to safe values
- Finish quickly—if your script might take a long time, convert it into a service and trigger actions through IPC or files

## Debugging scripts
1. Run the script manually: `python scripts/my_script.py --help`
2. Launch BindKit with `python main.py --minimized` and check `logs/app.log`
3. Use the Settings dialog to configure arguments and test `Run Now`
4. For subprocess scripts, inspect captured stdout/stderr in the BindKit notification

## Common pitfalls
- **No output**: Remember to `print(json.dumps(result))`
- **Stdout noise**: Extra prints corrupt the JSON payload; use logging or stderr
- **Missing guard**: Without `if __name__ == "__main__":` the analyzer may mis-detect entry points
- **Platform assumptions**: Wrap Windows-only imports/functions in platform guards

With these guidelines you can convert any automation idea into a BindKit-ready script in minutes.
