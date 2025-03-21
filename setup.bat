@echo off
setlocal enabledelayedexpansion

REM Check arguments
if "%1"=="--clean" (
    set CLEANUP_MODE=1
    echo Clean mode enabled. Virtual environment will be deleted after exit.
    echo.
) else (
    set CLEANUP_MODE=0
)

echo =======================================================
echo iRacing Fuel Usage Comparison Tool - Setup and Run
echo =======================================================
echo.

REM Check if Python is installed
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found. Please install Python.
    echo You can download it from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

REM Check if requirements.txt exists
if not exist requirements.txt (
    echo requirements.txt file not found.
    echo This file contains the necessary library information.
    pause
    exit /b 1
)

REM Check if venv folder exists in the current directory
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install required libraries
echo Installing required libraries...
python -m pip install --upgrade pip
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo Problem installing libraries.
    echo Please check the contents of requirements.txt.
    pause
    exit /b 1
)

echo All libraries installed successfully.
echo Installed packages:
pip freeze
echo.

REM Check for data directory
if not exist data (
    mkdir data
    echo Created data directory.
)

REM Run the application
echo Starting the application...
python run.py

REM Deactivate virtual environment
call venv\Scripts\deactivate.bat

REM If clean mode is active, delete the virtual environment
if %CLEANUP_MODE%==1 (
    echo Clean mode is active. Deleting virtual environment...
    rmdir /s /q venv
    echo Virtual environment deleted.
)

echo.
echo Application has ended.
echo Press any key to exit...
pause > nul