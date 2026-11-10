"""Compatibility import for :mod:`module1_intake.nlp.integration.persistence`."""
import sys as _sys
from .integration import persistence as _implementation

_sys.modules[__name__] = _implementation
