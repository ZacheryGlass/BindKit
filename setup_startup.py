#!/usr/bin/env python
"""
Standalone script to configure automatic startup for BindKit.
Can be run independently after setup to enable/disable startup.
"""

import sys
import os
import platform
import argparse

def setup_windows_startup(enable=True):
    """Configure Windows startup using registry."""
    try:
        import winreg
        
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "BindKit"
        
        # Get the path to run.bat
        app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.bat")
        
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
            if enable:
                # Add --minimized flag to start minimized
                command = f'"{app_path}" --minimized'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, command)
                print(f"✓ Enabled automatic startup for {app_name}")
                print(f"  Command: {command}")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    print(f"✓ Disabled automatic startup for {app_name}")
                except FileNotFoundError:
                    print(f"  {app_name} was not set to start automatically")
        return True
    except Exception as e:
        print(f"✗ Error configuring Windows startup: {e}")
        return False

def setup_linux_startup(enable=True):
    """Configure Linux startup using XDG autostart."""
    try:
        autostart_dir = os.path.expanduser("~/.config/autostart")
        desktop_file = os.path.join(autostart_dir, "bindkit.desktop")
        
        if enable:
            os.makedirs(autostart_dir, exist_ok=True)
            
            # Get the path to run.sh
            app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.sh")
            
            desktop_content = f"""[Desktop Entry]
Type=Application
Name=BindKit
Exec={app_path} --minimized
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Comment=BindKit Application
Icon=utilities-system-monitor
Categories=Utility;System;
"""
            
            with open(desktop_file, 'w') as f:
                f.write(desktop_content)
            
            os.chmod(desktop_file, 0o755)
            print(f"✓ Enabled automatic startup for BindKit")
            print(f"  Desktop file: {desktop_file}")
        else:
            if os.path.exists(desktop_file):
                os.remove(desktop_file)
                print(f"✓ Disabled automatic startup for BindKit")
            else:
                print("  BindKit was not set to start automatically")
        return True
    except Exception as e:
        print(f"✗ Error configuring Linux startup: {e}")
        return False

def setup_macos_startup(enable=True):
    """Configure macOS startup using LaunchAgent."""
    try:
        import subprocess
        
        launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")
        plist_file = os.path.join(launch_agents_dir, "com.bindkit.plist")
        
        if enable:
            os.makedirs(launch_agents_dir, exist_ok=True)
            
            # Get the path to run.sh
            app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.sh")
            
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.bindkit</string>
    <key>ProgramArguments</key>
    <array>
        <string>{app_path}</string>
        <string>--minimized</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/bindkit.err</string>
    <key>StandardOutPath</key>
    <string>/tmp/bindkit.out</string>
    <key>WorkingDirectory</key>
    <string>{os.path.dirname(app_path)}</string>
</dict>
</plist>"""
            
            with open(plist_file, 'w') as f:
                f.write(plist_content)
            
            # Load the launch agent
            subprocess.run(['launchctl', 'load', plist_file], check=False, capture_output=True)
            print(f"✓ Enabled automatic startup for BindKit")
            print(f"  LaunchAgent: {plist_file}")
        else:
            if os.path.exists(plist_file):
                # Unload the launch agent
                subprocess.run(['launchctl', 'unload', plist_file], check=False, capture_output=True)
                os.remove(plist_file)
                print(f"✓ Disabled automatic startup for BindKit")
            else:
                print("  BindKit was not set to start automatically")
        return True
    except Exception as e:
        print(f"✗ Error configuring macOS startup: {e}")
        return False

def check_startup_status():
    """Check if automatic startup is currently enabled."""
    system = platform.system()
    
    if system == "Windows":
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "BindKit"
            
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_QUERY_VALUE) as key:
                try:
                    value, _ = winreg.QueryValueEx(key, app_name)
                    print(f"✓ Automatic startup is ENABLED")
                    print(f"  Command: {value}")
                    return True
                except FileNotFoundError:
                    print("✗ Automatic startup is DISABLED")
                    return False
        except Exception as e:
            print(f"✗ Could not check startup status: {e}")
            return False
    
    elif system == "Linux":
        desktop_file = os.path.expanduser("~/.config/autostart/desktop-utility-gui.desktop")
        if os.path.exists(desktop_file):
            print(f"✓ Automatic startup is ENABLED")
            print(f"  Desktop file: {desktop_file}")
            return True
        else:
            print("✗ Automatic startup is DISABLED")
            return False
    
    elif system == "Darwin":
        plist_file = os.path.expanduser("~/Library/LaunchAgents/com.desktop-utility-gui.plist")
        if os.path.exists(plist_file):
            print(f"✓ Automatic startup is ENABLED")
            print(f"  LaunchAgent: {plist_file}")
            return True
        else:
            print("✗ Automatic startup is DISABLED")
            return False
    
    else:
        print(f"✗ Unsupported operating system: {system}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Configure automatic startup for BindKit"
    )
    parser.add_argument(
        'action',
        choices=['enable', 'disable', 'status'],
        help='Action to perform: enable/disable automatic startup or check status'
    )
    
    args = parser.parse_args()
    
    print("BindKit - Startup Configuration")
    print("=" * 45)
    print()
    
    if args.action == 'status':
        check_startup_status()
        return
    
    system = platform.system()
    enable = (args.action == 'enable')
    
    print(f"Operating System: {system}")
    print(f"Action: {'Enabling' if enable else 'Disabling'} automatic startup")
    print()
    
    success = False
    
    if system == "Windows":
        success = setup_windows_startup(enable)
    elif system == "Linux":
        success = setup_linux_startup(enable)
    elif system == "Darwin":  # macOS
        success = setup_macos_startup(enable)
    else:
        print(f"✗ Unsupported operating system: {system}")
        print("  Please configure startup manually for your system.")
        sys.exit(1)
    
    if success:
        print()
        print("Configuration completed successfully!")
        if enable:
            print("The application will start automatically on next login.")
        else:
            print("The application will no longer start automatically.")
    else:
        print()
        print("Configuration failed. Please check the error messages above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
