"""Offline DAV identification and direct DDInter mapping; no RxNorm dependency."""
from .ingredients import parse_ingredients
from .reference import MedicationReference, build_reference
from .service import identify, from_module1, assess_prescriptions
from .terminology import DirectDDInter, load_ddinter

__all__ = ['parse_ingredients', 'MedicationReference', 'build_reference', 'identify',
           'from_module1', 'assess_prescriptions', 'DirectDDInter', 'load_ddinter']


def __getattr__(name):
    # Keep legacy offline callers independent of the optional PostgreSQL dependency.
    if name in {'CoreMedicationReference', 'identify_confirmed'}:
        from . import core
        return getattr(core, name)
    raise AttributeError(name)


__all__ += ['CoreMedicationReference', 'identify_confirmed']
