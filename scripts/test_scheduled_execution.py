#!/usr/bin/env python3
"""
Test script for scheduled execution verification.

This script writes a timestamp to a log file when executed.
Use this to verify that scheduled task execution is working correctly.

The script will:
1. Create/append to a log file in the application directory
2. Write the current timestamp and execution count
3. Return success status

Usage: Configure a schedule for this script to verify:
- Scheduled execution works
- Overlap prevention (won't run if previous execution still running)
- Settings persistence (timestamps survive app restart)
"""

import argparse
import json
import logging
from pathlib import Path
from datetime import datetime
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Test scheduled execution')
    parser.add_argument('--execution-number', type=int, default=1, help='Execution number for testing')
    parser.add_argument('--delay', type=float, default=0, help='Delay in seconds before completing (for overlap testing)')
    args = parser.parse_args()

    try:
        # Get the log file path
        app_dir = Path(__file__).parent.parent
        log_file = app_dir / 'scheduled_execution_test.log'

        # Simulate some work
        if args.delay > 0:
            logger.info(f"Delaying execution for {args.delay} seconds...")
            time.sleep(args.delay)

        # Write execution record
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] Execution #{args.execution_number}\n")

        logger.info(f"Scheduled execution completed at {timestamp}")

        result = {
            'success': True,
            'message': f'Scheduled execution completed at {timestamp}',
            'timestamp': timestamp,
            'execution_number': args.execution_number
        }

        print(json.dumps(result))
        return 0

    except Exception as e:
        logger.error(f"Error during scheduled execution: {e}")

        result = {
            'success': False,
            'message': f'Scheduled execution failed: {str(e)}'
        }

        print(json.dumps(result))
        return 1


if __name__ == '__main__':
    exit(main())
