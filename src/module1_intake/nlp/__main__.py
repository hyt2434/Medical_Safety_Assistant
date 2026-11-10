"""Compatibility entry point; existing PowerShell launchers keep this module path."""
import sys as _sys
from .interfaces import cli as _implementation

if __name__ == '__main__':
    _implementation.main()
else:
    _sys.modules[__name__] = _implementation
