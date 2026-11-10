"""Compatibility import for :mod:`module1_intake.nlp.dialogue_management.manager`."""
import sys as _sys
from .dialogue_management import manager as _implementation

_sys.modules[__name__] = _implementation
