@echo off
REM Test script for repository components

cd C:\AI\Nova
call venv\Scripts\activate.bat

echo Running repository import test
python src\ui\test_repository_import.py
echo Done with import test

echo Running repository config test
python src\ui\test_repository_config.py
echo Done with config test

echo Tests complete
pause