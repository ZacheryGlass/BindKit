#!/bin/bash
# Example Shell Script for BindKit
# This script demonstrates Shell script support

# Default message
MESSAGE="Hello from Shell!"

# Parse command line arguments
while getopts "m:h" opt; do
    case $opt in
        m) # Message
            MESSAGE="$OPTARG"
            ;;
        h) # Help
            echo "Usage: $0 [-m message]"
            echo "  -m MESSAGE    Custom message to display"
            exit 0
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            exit 1
            ;;
    esac
done

echo "========================================"
echo "BindKit Shell Script Example"
echo "========================================"
echo ""
echo "Message: $MESSAGE"
echo ""
echo "Shell script executed successfully"

# Exit with success code
exit 0
