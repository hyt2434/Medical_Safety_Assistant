"""Compatibility import for :mod:`module1_intake.nlp.dialogue_management.fsm`."""
import sys as _sys
from .dialogue_management import fsm as _implementation

_sys.modules[__name__] = _implementation
