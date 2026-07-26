"""
Thin wrapper plugin for EnergyPlus PythonPlugin.
Adds src/ to sys.path and re-exports the Controller and register_callbacks
from the ecoloop package so the IDF can use module "plugin" and class "Controller".
"""
import sys
from pathlib import Path

# Ensure the src directory (containing ecoloop package) is on sys.path
SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ecoloop.plugin import Controller, register_callbacks

# Expose for EnergyPlus plugin loader
__all__ = ["Controller", "register_callbacks"]