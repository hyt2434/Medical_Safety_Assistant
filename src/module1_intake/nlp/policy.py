"""Compatibility import for :mod:`module1_intake.nlp.dialogue_management.policy`."""
import sys as _sys
from .dialogue_management import policy as _implementation

_sys.modules[__name__] = _implementation
