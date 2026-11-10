"""Compatibility import for :mod:`module1_intake.nlp.interfaces.application`."""
import sys as _sys
from .interfaces import application as _implementation

_sys.modules[__name__] = _implementation
