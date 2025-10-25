# BindKit Scheduler Guide

A comprehensive guide to using and developing with BindKit's built-in scheduler for automated script execution.

## Table of Contents

1. [Overview](#overview)
2. [For Users](#for-users)
3. [For Developers](#for-developers)
4. [Technical Details](#technical-details)
5. [Best Practices](#best-practices)
6. [Troubleshooting](#troubleshooting)
7. [FAQ](#faq)

## Overview

BindKit includes a built-in scheduler that automatically executes scripts at regular intervals. The scheduler uses Qt's QTimer for reliable, efficient scheduling without external dependencies.

### Key Features

- **Simple Configuration**: Enable scheduling with a few clicks in the Settings dialog
- **Flexible Intervals**: Support for seconds, minutes, hours, and days
- **Overlap Prevention**: Automatically prevents multiple simultaneous executions
- **Persistent Storage**: Schedules survive application restarts
- **Real-time Monitoring**: View last run and next scheduled times
- **Manual Control**: Force immediate execution with "Run Now" button

### What is Scheduling For?

Scheduling is ideal for:
- Regular system maintenance tasks
- Periodic data backups or syncs
- Health checks and monitoring
- Automated cleanup operations
- Time-based status updates
- Recurring administrative tasks

Not recommended for:
- Real-time requirements (< 1 second precision)
- Complex sequential workflows (use scripts instead)
- High-frequency operations (> 1 per second)

---

## For Users

### Quick Start

1. **Open Schedule Settings**
   - Right-click the BindKit system tray icon
   - Select "Settings..."
   - Click the "Schedule" tab

2. **Enable a Schedule**
   - Select a script from the list
   - Check the "Enable Schedule" checkbox
   - Set the interval (value + unit)
   - Click "OK" to save

3. **Monitor Execution**
   - Return to Settings > Schedule tab
   - View "Last run" timestamp
   - View "Next run" timestamp
   - Check status indicator

### Understanding Intervals

**Supported Units:**

| Unit | Best For | Examples |
|------|----------|----------|
| **Seconds** | Quick checks, testing | 10s, 30s, 60s |
| **Minutes** | Regular updates | 5 min, 15 min, 30 min |
| **Hours** | Daily maintenance | 1 hour, 4 hours, 12 hours |
| **Days** | Weekly tasks | 1 day, 7 days |

**Interval Limits:**
- Minimum: 10 seconds (prevents system overload)
- Maximum: ~24.8 days (technical limitation of Qt's QTimer)
- Maximum total seconds: 2,147,483 (unsigned 32-bit)

### Configuring Multiple Schedules

You can schedule multiple scripts simultaneously:

1. Each script can have its own interval
2. Schedules run independently (one delay doesn't affect others)
3. Application manages all timers automatically
4. All schedules saved together in settings

Example configuration:
```
Backup Script:     Every 1 hour
Status Check:      Every 15 minutes
Maintenance Task:  Every 1 day
Log Cleanup:       Every 7 days
```

### Overlap Prevention

Overlap prevention ensures reliability by preventing script execution collisions.

**What happens:**
- If a script is still running when the next interval arrives, that execution is skipped
- Prevents resource exhaustion and cascading failures
- Logged in application (check debug logs)

**Example scenario:**
```
Interval:              10 minutes
Typical execution:     5 minutes
Next execution:        On schedule (5 min < 10 min)

Interval:              10 minutes
Slow execution:        15 minutes (delayed by system)
Next execution:        SKIPPED (still running)
Following execution:   On next interval (10 min after start)
```

**How to detect:**
- Script not running as frequently as expected
- Check last run vs next run times
- Look for gaps in execution log
- Use "Run Now" to verify script still works

**How to fix:**
- Increase interval to be longer than execution time
- Example: 15-minute execution → use 20+ minute interval
- Monitor first few executions for timing

### Using "Run Now"

The "Run Now" button lets you execute a scheduled script immediately:

1. Select script from list
2. Click "Run Now"
3. Script executes immediately (unless already running)
4. UI updates with new "Last run" time
5. "Next run" is recalculated

**Use cases:**
- Test script before relying on automation
- Verify overlap prevention is working
- Force execution for urgent tasks
- Debug script behavior

### Viewing Execution Times

**Last Run:**
- Format: YYYY-MM-DD HH:MM:SS
- "Never" = script hasn't executed yet
- Updates immediately after execution
- Stored persistently in settings

**Next Run:**
- Format: YYYY-MM-DD HH:MM:SS
- Calculated as: now + interval
- Updates after each execution
- Shows when script will next run

**Example:**
```
Now:        2024-01-15 14:30:00
Interval:   1 hour (3600 seconds)
Last Run:   2024-01-15 13:30:00
Next Run:   2024-01-15 14:30:00 (already scheduled)
           -> 2024-01-15 15:30:00 (after execution)
```

### Persistence and Auto-start

All schedule settings persist across restarts:

**What's saved:**
- Enabled/disabled state for each script
- Interval (value + unit)
- Last run timestamp
- Next run timestamp

**What happens on restart:**
1. Application loads settings
2. Previously enabled schedules are automatically started
3. Timestamps are restored from saved settings
4. Execution resumes on schedule

**Important:**
- Schedules survive application crashes
- Clean exit (right-click > Exit) saves state properly
- Never manually edit settings files

### Disable/Remove Schedules

**Temporarily disable:**
- Open Settings > Schedule
- Uncheck "Enable Schedule" for a script
- Click OK

**Permanently remove:**
- Disable the schedule
- Schedule won't be saved or started on next launch

### Common Tasks

**Run cleanup every morning at specific time:**
- Unfortunately, scheduler only supports fixed intervals
- Workaround: Use a 24-hour interval starting at midnight
- Consider using OS task scheduler for specific times

**Run different schedules on weekdays vs weekends:**
- Scheduler doesn't support day-based conditions
- Workaround: Create two scripts with different logic
- Have each schedule run daily

**Run every 4 hours during business hours only:**
- Scheduler can't be conditional on time of day
- Workaround: Add logic inside your script to check time
- Return success but do nothing if outside business hours

---

## For Developers

### Programmatic Scheduler Usage

Access the scheduler directly in application code:

```python
from core.schedule_runtime import ScheduleRuntime
from pathlib import Path

# Create scheduler
scheduler = ScheduleRuntime()

# Define what to do when schedule fires
def execute_my_script(script_name: str):
    print(f"Executing {script_name}")
    executor.execute_script_by_name(script_name)

# Start a schedule
handle = scheduler.start_schedule(
    script_name="my_script",
    script_path=Path("scripts/my_script.py"),
    interval_seconds=3600,  # 1 hour
    execution_callback=execute_my_script,
    settings_manager=settings  # Optional
)

# Connect to signals
scheduler.schedule_started.connect(on_schedule_started)
scheduler.schedule_executed.connect(on_schedule_executed)
scheduler.schedule_error.connect(on_schedule_error)

# Check status
if scheduler.is_scheduled("my_script"):
    info = scheduler.get_schedule_info("my_script")
    print(f"Last run: {info['last_run']}")
    print(f"Next run: {info['next_run']}")

# Update interval
scheduler.update_interval("my_script", 7200)  # 2 hours

# Stop schedule
scheduler.stop_schedule("my_script")

# Stop all schedules (on shutdown)
scheduler.stop_all_schedules()
```

### Scheduler API Summary

#### Start Schedule
```python
handle = scheduler.start_schedule(
    script_name: str,
    script_path: Path,
    interval_seconds: int,
    execution_callback: Callable,
    settings_manager = None
) -> ScheduleHandle
```

Raises:
- `ValueError`: Interval outside 10s to ~24.8 days
- `RuntimeError`: Schedule already exists for script

#### Stop Schedule
```python
success = scheduler.stop_schedule(script_name: str) -> bool
```

#### Check if Scheduled
```python
is_active = scheduler.is_scheduled(script_name: str) -> bool
```

#### Get Schedule Info
```python
info = scheduler.get_schedule_info(script_name: str) -> Optional[Dict]
```

Returns dict with:
- `script_name`: Script name
- `interval_seconds`: Interval in seconds
- `last_run`: Timestamp of last execution
- `next_run`: Timestamp of next scheduled execution
- `is_executing`: Currently running flag
- `state`: Schedule state (STOPPED, SCHEDULED, RUNNING, ERROR)

#### Update Interval
```python
success = scheduler.update_interval(script_name: str, new_interval_seconds: int) -> bool
```

Raises:
- `ValueError`: Interval outside valid range

#### Get All Schedules
```python
schedules = scheduler.get_all_schedules() -> Dict[str, ScheduleHandle]
```

#### Stop All Schedules
```python
count = scheduler.stop_all_schedules() -> int
```

### Signals

Connect to scheduler events:

```python
scheduler.schedule_started.connect(on_started)
scheduler.schedule_stopped.connect(on_stopped)
scheduler.schedule_executed.connect(on_executed)
scheduler.schedule_error.connect(on_error)
scheduler.schedule_execution_blocked.connect(on_blocked)

def on_started(script_name: str):
    print(f"Schedule started: {script_name}")

def on_stopped(script_name: str):
    print(f"Schedule stopped: {script_name}")

def on_executed(script_name: str):
    print(f"Execution completed: {script_name}")

def on_error(script_name: str, error_msg: str):
    print(f"Error in {script_name}: {error_msg}")

def on_blocked(script_name: str):
    print(f"Execution skipped (overlap): {script_name}")
```

### Writing Scheduler-Compatible Scripts

Scripts can be scheduled like any other scripts, but should follow these patterns:

#### Standalone Script Example
```python
#!/usr/bin/env python3
"""Script suitable for scheduled execution"""
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    try:
        logger.info("Scheduled execution started")

        # Your work here
        result = perform_work()

        logger.info("Scheduled execution completed")

        return {
            'success': True,
            'message': 'Work completed successfully',
            'data': result
        }

    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        return {
            'success': False,
            'message': str(e)
        }

if __name__ == '__main__':
    import sys
    result = main()
    print(json.dumps(result))
    sys.exit(0 if result['success'] else 1)
```

#### Legacy UtilityScript Example
```python
import sys
sys.path.append('..')

from core.base_script import UtilityScript
from core.button_types import ButtonType

class SchedulableScript(UtilityScript):
    def get_metadata(self):
        return {
            'name': 'My Scheduled Task',
            'description': 'Runs on a schedule',
            'button_type': ButtonType.RUN
        }

    def get_status(self):
        return "Ready for scheduling"

    def execute(self):
        # Good for scheduling: no parameters, quick execution
        try:
            result = perform_work()
            return {'success': True, 'message': 'Work completed'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def validate(self):
        return True
```

### Thread Safety

The scheduler is thread-safe:

- Uses `threading.Lock` for schedule operations
- Safe to call from multiple threads
- Safe to have callback execute long-running tasks
- Exception in callback won't crash scheduler

### Error Handling

Schedule errors are emitted as signals:

```python
def on_schedule_error(script_name: str, error_msg: str):
    logger.error(f"Schedule error in {script_name}: {error_msg}")
    # Take action: notify user, disable schedule, etc.

scheduler.schedule_error.connect(on_schedule_error)
```

---

## Technical Details

### Implementation

BindKit's scheduler uses Qt's QTimer for reliability:

- **QTimer**: Native Qt timer integrated with event loop
- **No external dependencies**: No cron, systemd, or Task Scheduler
- **Cross-platform ready**: Core code is platform-agnostic
- **Event-driven**: Integrates with Qt event loop

### Interval Validation

Intervals are constrained by QTimer limitations:

```
Minimum: 10 seconds (MIN_INTERVAL_SECONDS)
Maximum: 2,147,483 seconds (~24.8 days)
Reason: QTimer uses 32-bit signed millisecond values
```

Conversion to milliseconds (internal):
```
interval_ms = interval_seconds * 1000
Max: 2,147,483 * 1000 = 2,147,483,000 ms
QTimer limit: 2^31 - 1 = 2,147,483,647 ms
```

### Overlap Prevention Mechanism

When scheduled execution time arrives:

```
1. Check: is_executing flag
2. If true: emit schedule_execution_blocked signal, exit
3. If false: set is_executing = true
4. Call execution callback
5. On completion: set is_executing = false
```

Prevents concurrent execution without complex locking.

### Timestamp Management

Timestamps are stored as Unix epoch (float seconds):

```python
import time
timestamp = time.time()  # Returns float seconds since epoch
dt = datetime.fromtimestamp(timestamp)  # Convert to datetime
```

Stored in application settings for persistence.

### State Management

Schedule states during lifecycle:

```
SCHEDULED -> RUNNING -> SCHEDULED
         \-> ERROR (on exception)
              -> SCHEDULED (after recovery)

SCHEDULED/RUNNING -> STOPPED (on stop_schedule)
```

State can be queried via `get_schedule_status()`.

### Signal Flow

```
Application Start
    |
    +-> Load Settings (including schedules)
    |
    +-> MainWindow loads ScheduleRuntime
    |
    +-> For each enabled schedule:
    |   |
    |   +-> start_schedule()
    |   |   |
    |   |   +-> Create QTimer
    |   |   |
    |   |   +-> timer.start(interval_ms)
    |   |   |
    |   |   +-> emit schedule_started
    |   |
    |   +-> Connect signals
    |
    +-> On interval timeout:
    |   |
    |   +-> _execute_scheduled_task()
    |   |
    |   +-> Check overlap, execute callback
    |   |
    |   +-> emit schedule_executed or schedule_error
    |
    +-> On application shutdown:
        |
        +-> stop_all_schedules()
            |
            +-> Stop all timers
            |
            +-> Disconnect signals
            |
            +-> Save final state
```

---

## Best Practices

### For Users

1. **Set realistic intervals**: Scripts with 15-minute typical runtime should have 20+ minute intervals
2. **Monitor first few executions**: Verify timing works as expected
3. **Use "Run Now" for testing**: Don't wait for next interval to verify functionality
4. **Document your schedules**: Keep notes on what's scheduled and why
5. **Review logs periodically**: Check for unexpected errors or skipped executions

### For Developers

1. **Make scripts idempotent**: Safe to run multiple times
2. **Add timeout to operations**: Prevent hanging
3. **Return JSON status**: Always include success/failure indicator
4. **Handle errors gracefully**: Never crash the scheduler
5. **Log important events**: Help users debug issues
6. **Test overlap scenarios**: Verify with longer execution times
7. **Use appropriate intervals**: 10s minimum, ~24.8 days maximum
8. **Clean up resources**: Ensure scheduled scripts don't leak memory/files

### Schedule Design Patterns

**Quick checks (every minute or less):**
```python
# Use seconds, e.g., 60 second interval
# Keep execution time < 60 seconds
# Return quickly even if nothing to do
```

**Regular maintenance (every few hours):**
```python
# Use hours, e.g., 4 hour interval
# Can have longer execution time (e.g., 10-15 minutes)
# Set interval to 2x expected execution time
```

**Daily tasks (every day):**
```python
# Use days, e.g., 1 day interval
# Execution can take minutes/hours
# Consider performance impact on system
# Ensure idempotency (safe to run anytime)
```

---

## Troubleshooting

### Schedule Not Running

**Symptoms:**
- Script never executes
- Last run stays "Never"

**Diagnosis:**
1. Open Settings > Schedule tab
2. Is "Enable Schedule" checked? (Must be checked)
3. Is there an interval set? (Should show number + unit)
4. Is application in system tray? (Must be running)

**Solutions:**
- Enable the schedule if disabled
- Set interval to valid value
- Restart application
- Check application logs for errors

### Execution Too Frequent or Too Rare

**Symptoms:**
- Script runs more often than expected
- Script runs less often than expected

**Diagnosis:**
1. Note the configured interval
2. Check "Last run" timestamps
3. Calculate actual interval between executions
4. Compare to configured interval

**Solutions:**
- Verify interval setting matches intent (e.g., 5 minutes, not 5 seconds)
- Check for execution blocking due to overlap
- Review script execution time

### Overlapping Executions

**Symptoms:**
- Script scheduled every 5 minutes but misses some runs
- Gap in "Last run" timestamps
- Execution blocked messages in logs

**Diagnosis:**
1. Check typical script execution time
2. Compare to configured interval
3. If execution time > interval, overlaps occur

**Solution:**
- Increase interval to be 1.5-2x execution time
- Example: 10-minute execution → 20+ minute interval

### Settings Not Persisting

**Symptoms:**
- Schedule settings lost after restart
- Schedules don't auto-start

**Diagnosis:**
1. Was application closed cleanly? (Use Exit menu)
2. Disk full? Check available space
3. Permissions issue? Check folder is writable

**Solutions:**
- Always exit via menu (right-click tray > Exit)
- Check disk space
- Verify folder permissions
- Run as administrator if needed

### Script Returns Wrong Format

**Symptoms:**
- Execution succeeds but shows errors
- UI doesn't update properly

**Diagnosis:**
- Script not returning JSON?
- Check script output format

**Solution:**
- Ensure script prints: `{"success": true/false, "message": "..."}`
- Test: `python scripts/your_script.py`

### "Interval must be at least 10 seconds"

**Symptom:** Error when trying to set interval < 10 seconds

**Solution:**
- Minimum interval is 10 seconds (prevents system overload)
- Use a longer interval
- If you need faster execution, use hotkeys instead

### "Interval exceeds maximum"

**Symptom:** Error when trying to set interval > ~24.8 days

**Solution:**
- Maximum is ~24.8 days (technical limit)
- Use next smaller unit or break into multiple schedules
- Example: 25 days → 1 month with custom script logic

---

## FAQ

**Q: Can I run multiple scripts at the same time?**
A: Yes, different schedules run independently. Each script can execute on its own interval.

**Q: What if my script takes longer than the interval?**
A: Overlap prevention skips the next execution. Increase interval to be 1.5-2x execution time.

**Q: Do schedules survive application crashes?**
A: Yes, settings are saved persistently. When app restarts, schedules resume on schedule.

**Q: Can I schedule for specific times (e.g., 2 PM)?**
A: Not directly. Scheduler uses fixed intervals only. Workaround: Add time-of-day logic in your script.

**Q: Can I run a script on weekends only?**
A: Not directly. Workaround: Add day-of-week logic in your script, return success silently if not matching.

**Q: How precise is the scheduling?**
A: Typical precision is within 50-100ms. Not suitable for real-time requirements.

**Q: Can I edit schedules while application is running?**
A: Yes, all changes take effect immediately. Changes saved to settings.

**Q: What happens if I disable a schedule?**
A: Script stops executing. Schedule settings are saved. Re-enable anytime.

**Q: Can I have different intervals for the same script?**
A: Not simultaneously. Only one schedule per script, but you can change it anytime.

**Q: Is there a limit on number of schedules?**
A: No hard limit, but many schedules may impact performance. Typical systems handle 50+ without issues.

**Q: Where are schedule settings stored?**
A: Windows: `%APPDATA%/BindKit/settings.ini`
Linux/Mac: `~/.config/BindKit/settings.conf`

**Q: Can I manually edit settings files?**
A: Not recommended. Use the UI to modify schedules. Manual edits can corrupt settings.

**Q: How do I backup my schedules?**
A: Copy the settings file (see above). Restore by copying back (app must be closed).

**Q: What if the system is asleep during scheduled execution?**
A: Schedule won't execute while system sleeps. Executes when system wakes up (approximately).

**Q: Can I schedule Windows built-in tasks?**
A: BindKit can only schedule its own scripts. Use Windows Task Scheduler for native tasks.
