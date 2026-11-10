"""Compatibility import for :mod:`module1_intake.nlp.interfaces.application_cli`."""
import sys as _sys
from .interfaces import application_cli as _implementation

_sys.modules[__name__] = _implementation
