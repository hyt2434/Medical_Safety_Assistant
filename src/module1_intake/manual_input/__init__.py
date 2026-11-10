"""PLANNED: independent structured medication form input, separate from NLP.

Required form fields: medication name, strength, and dosage form.
Planned flow: structured form -> Module 2 lookup/autocomplete when available ->
user verification/correction -> common confirmed Module 1 medication data ->
Module 2 identification -> Module 3 DDI assessment.

Preserve unresolved or ambiguous product identities. Never guess missing fields
or automatically confirm identities. Typed natural-language requests belong to
NLP. Reuse the shared.intake output contract when implementing the adapter;
structured-form validation and dosage-form representation remain to be defined.

UI, backend form, lookup integration and confirmation adapter are not implemented.
"""

STATUS = "PLANNED"

__all__ = ("STATUS",)
