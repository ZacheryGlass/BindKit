@echo off
REM Example Batch Script for BindKit
REM This script demonstrates Batch script support

REM %1 - Message to display
REM %2 - Optional second parameter

if "%~1"=="" (
    set MESSAGE=Hello from Batch!
) else (
    set MESSAGE=%~1
)

echo ========================================
echo BindKit Batch Script Example
echo ========================================
echo.
echo Message: %MESSAGE%
echo.

REM Display a message box using PowerShell (Windows only)
powershell -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('%MESSAGE%', 'BindKit Batch Example', 'OK', 'Information')"

echo.
echo Batch script executed successfully
exit /b 0
