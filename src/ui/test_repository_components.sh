#!/bin/bash
# Test script for repository components

cd /mnt/c/AI/Nova

if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Virtual environment activation script not found."
    exit 1
fi

echo "Running repository import test"
python src/ui/test_repository_import.py
echo "Done with import test"

echo "Running repository config test"
python src/ui/test_repository_config.py
echo "Done with config test"

echo "Tests complete"