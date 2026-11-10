"""Compatibility import for :mod:`module1_intake.nlp.interfaces.interactive`."""
import sys as _sys
from .interfaces import interactive as _implementation

_sys.modules[__name__] = _implementation
