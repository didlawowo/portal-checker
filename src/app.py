"""
Portal Checker - Legacy app.py file for backwards compatibility
This file is now a thin wrapper around the refactored modules.
"""

# Import everything from the new main module
from .main import main, setup_logger
from .api import app
from .config import *
from .utils import get_app_version


# For backwards compatibility, expose the main Flask app
__all__ = ['app', 'main', 'setup_logger', 'get_app_version']


# Entry point when running as a module
if __name__ == "__main__":
    main()