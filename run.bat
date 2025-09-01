@echo off
if not exist "venv" (
    echo Virtual environment not found. Running setup first...
    call setup.bat
    if %errorlevel% neq 0 (
        exit /b 1
    )
)

echo Starting BindKit...
call venv\Scripts\activate.bat && python main.py
pause
