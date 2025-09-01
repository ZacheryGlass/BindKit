@echo off
echo BindKit Setup
echo =========================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://www.python.org/
    pause
    exit /b 1
)

echo Creating virtual environment...
python -m venv venv

if not exist "venv" (
    echo Error: Failed to create virtual environment
    pause
    exit /b 1
)

echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing required packages...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo Error: Failed to install some packages
    echo Please check the error messages above
    pause
    exit /b 1
)

echo.
echo =========================
echo Setup completed successfully!
echo =========================
echo.

REM Ask about startup
echo Would you like to run BindKit automatically when Windows starts?
set /p startup_choice="Enter Y for Yes, N for No (default: N): "

if /i "%startup_choice%"=="Y" (
    echo.
    echo Setting up automatic startup...
    
    REM Create a simple Python script to enable startup
    call venv\Scripts\activate.bat
    python -c "from core.startup_manager import StartupManager; sm = StartupManager('BindKit'); sm.enable(); print('Startup enabled successfully!')" 2>nul
    
    if %errorlevel% equ 0 (
        echo BindKit will now start automatically with Windows.
        echo You can disable this later in the application settings.
    ) else (
        echo Note: Could not enable automatic startup at this time.
        echo You can enable it later from the application settings.
    )
) else (
    echo.
    echo Automatic startup not enabled. You can enable it later in the application settings.
)

echo.
echo =========================
echo To run the application:
echo   1. Run: venv\Scripts\activate.bat
echo   2. Run: python main.py
echo.
echo Or simply run: run.bat
echo =========================
pause
