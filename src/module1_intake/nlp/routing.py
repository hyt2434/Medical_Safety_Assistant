"""Compatibility import for :mod:`module1_intake.nlp.understanding.routing`."""
import sys as _sys
from .understanding import routing as _implementation

_sys.modules[__name__] = _implementation
