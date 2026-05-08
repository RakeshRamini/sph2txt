"""Silent launcher for sph2txt (no console window)."""
import os
import sys

# Ensure we're in the project directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Use the venv's Python
venv_python = os.path.join("s2tenv", "Scripts", "python.exe")
if os.path.exists(venv_python):
    os.execv(venv_python, [venv_python, "-m", "src.main"])
else:
    sys.exit("Virtual environment not found.")
