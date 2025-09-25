#!/usr/bin/env python3
"""
Audio Toggle Script

Toggles between available audio output devices on Windows.
This script requires nircmd.exe or AudioDeviceCmdlets PowerShell module.
"""

import subprocess
import sys
import json
from pathlib import Path
from typing import Dict, Any, List


def _get_state_file() -> Path:
    """Get the state file path for audio device tracking."""
    state_file = Path.home() / '.desktop_utility_gui' / 'audio_device_state.json'
    state_file.parent.mkdir(parents=True, exist_ok=True)
    return state_file


def _load_saved_state() -> Dict[str, Any]:
    """Load the saved audio device state from file."""
    state_file = _get_state_file()
    try:
        if state_file.exists():
            with open(state_file, 'r') as f:
                data = json.load(f)
                return {
                    'devices': data.get('devices', []),
                    'current_index': data.get('current_index', 0)
                }
    except Exception:
        pass
    return {'devices': [], 'current_index': 0}


def _save_state(devices: List[str], current_index: int) -> None:
    """Save the current audio device state to file."""
    state_file = _get_state_file()
    try:
        with open(state_file, 'w') as f:
            json.dump({
                'devices': devices,
                'current_index': current_index
            }, f, indent=2)
    except Exception:
        pass


def _get_audio_devices() -> List[str]:
    """Get list of available audio output devices using PowerShell."""
    try:
        # PowerShell script to get audio devices
        ps_script = """
        Add-Type @'
        using System;
        using System.Runtime.InteropServices;
        using System.Collections.Generic;
        
        public class AudioDevice {
            [DllImport("winmm.dll", CharSet = CharSet.Auto)]
            public static extern int waveOutGetNumDevs();
            
            [DllImport("winmm.dll", CharSet = CharSet.Auto)]
            public static extern int waveOutGetDevCaps(int uDeviceID, ref WAVEOUTCAPS pwoc, int cbwoc);
            
            [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
            public struct WAVEOUTCAPS {
                public short wMid;
                public short wPid;
                public int vDriverVersion;
                [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
                public string szPname;
                public uint dwFormats;
                public short wChannels;
                public short wReserved1;
                public uint dwSupport;
            }
            
            public static List<string> GetDevices() {
                var devices = new List<string>();
                int numDevs = waveOutGetNumDevs();
                for (int i = 0; i < numDevs; i++) {
                    WAVEOUTCAPS caps = new WAVEOUTCAPS();
                    if (waveOutGetDevCaps(i, ref caps, Marshal.SizeOf(caps)) == 0) {
                        devices.Add(caps.szPname);
                    }
                }
                return devices;
            }
        }
'@
        
        [AudioDevice]::GetDevices() | ConvertTo-Json
        """
        
        result = subprocess.run(
            ['powershell', '-Command', ps_script],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        if result.returncode == 0 and result.stdout:
            devices = json.loads(result.stdout)
            if isinstance(devices, list):
                return devices
            elif isinstance(devices, str):
                return [devices]
        
        # Fallback: use simpler PowerShell command
        ps_script_simple = """
        Get-CimInstance -ClassName Win32_SoundDevice | Where-Object {$_.Status -eq 'OK'} | Select-Object -ExpandProperty Name | ConvertTo-Json
        """
        
        result = subprocess.run(
            ['powershell', '-Command', ps_script_simple],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        if result.returncode == 0 and result.stdout:
            devices = json.loads(result.stdout)
            if isinstance(devices, list):
                return devices
            elif isinstance(devices, str):
                return [devices]
                
    except Exception:
        pass
    
    return []


def _set_default_audio_device(device_index: int, devices: List[str]) -> bool:
    """Set the default audio output device using nircmd."""
    try:
        # First, try using nircmd if available
        nircmd_path = Path('C:/Windows/nircmd.exe')
        if not nircmd_path.exists():
            nircmd_path = Path('nircmd.exe')
        
        if nircmd_path.exists():
            # nircmd setdefaultsounddevice <device_name>
            if device_index < len(devices):
                device_name = devices[device_index]
                result = subprocess.run(
                    [str(nircmd_path), 'setdefaultsounddevice', device_name],
                    capture_output=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                return result.returncode == 0
        
        # Fallback: Use PowerShell with AudioDeviceCmdlets module (if installed)
        ps_script = f"""
        # Try to import AudioDeviceCmdlets module
        try {{
            Import-Module AudioDeviceCmdlets -ErrorAction Stop
            $devices = Get-AudioDevice -List
            if ($devices.Count -gt {device_index}) {{
                Set-AudioDevice -Index {device_index}
                exit 0
            }}
        }} catch {{
            # Module not available
        }}
        
        # Alternative: Use Windows Audio Session API
        Add-Type @'
        using System;
        using System.Runtime.InteropServices;
        
        public class AudioSwitcher {{
            [DllImport("ole32.dll")]
            public static extern int CoInitialize(IntPtr pvReserved);
            
            public static void SetDevice(int index) {{
                CoInitialize(IntPtr.Zero);
                // This is a simplified version - full implementation would require COM interop
            }}
        }}
'@
        
        # For now, return error code to indicate we need nircmd or AudioDeviceCmdlets
        exit 1
        """
        
        result = subprocess.run(
            ['powershell', '-Command', ps_script],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        return result.returncode == 0
        
    except Exception:
        return False


def get_current_status() -> str:
    """Return the current audio device name."""
    state = _load_saved_state()
    devices = state['devices']
    current_index = state['current_index']
    
    if devices and current_index < len(devices):
        device_name = devices[current_index]
        # Truncate long device names for display
        if len(device_name) > 20:
            return device_name[:17] + '...'
        return device_name
    return 'No Device'


def toggle_audio_device() -> Dict[str, Any]:
    """Toggle to the next audio output device."""
    if sys.platform != 'win32':
        return {
            'success': False,
            'message': 'Audio toggle only supported on Windows'
        }
    
    try:
        # Load current state
        state = _load_saved_state()
        current_devices = state['devices']
        current_index = state['current_index']
        
        # Refresh device list
        devices = _get_audio_devices()
        
        if not devices:
            return {
                'success': False,
                'message': 'No audio output devices found'
            }
        
        # Update device list if changed
        if devices != current_devices:
            current_devices = devices
            current_index = 0
        
        # Calculate next device index
        next_index = (current_index + 1) % len(current_devices)
        
        # Try to set the audio device
        if _set_default_audio_device(next_index, current_devices):
            # Save new state
            _save_state(current_devices, next_index)
            
            return {
                'success': True,
                'message': f'Switched to: {current_devices[next_index]}',
                'new_status': current_devices[next_index][:20] + ('...' if len(current_devices[next_index]) > 20 else '')
            }
        else:
            # If setting device failed, inform user about nircmd
            return {
                'success': False,
                'message': 'Audio switch requires nircmd.exe in C:\\Windows\\ or AudioDeviceCmdlets PowerShell module'
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'Error toggling audio device: {str(e)}'
        }


def validate_system() -> bool:
    """Check if audio toggling is available on this system."""
    if sys.platform != 'win32':
        return False
    
    try:
        # Check if we can get audio devices
        devices = _get_audio_devices()
        # Script is valid if we have at least 1 audio device
        return len(devices) >= 1
    except:
        return False


def main():
    """Main execution function."""
    if not validate_system():
        result = {
            'success': False,
            'message': 'Audio toggle not available on this system'
        }
        print(json.dumps(result))
        return 1
    
    current_status = get_current_status()
    print(f"Current audio device: {current_status}")
    
    print("Toggling audio output device...")
    result = toggle_audio_device()
    
    print(json.dumps(result, indent=2))
    return 0 if result.get('success', False) else 1


if __name__ == "__main__":
    sys.exit(main())