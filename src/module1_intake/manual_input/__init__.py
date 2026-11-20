"""Medication dictionary and name suggestions, separate from NLP.

Required form fields: medication name, strength, and dosage form.
Flow: autocomplete -> explicit product selection + structured form -> persisted
Module 1 review/edit/confirmation -> Module 2 identification -> Module 3 DDI.

Preserve unresolved or ambiguous product identities. Never guess missing fields
or automatically confirm identities. Typed natural-language requests belong to
NLP. The application uses the unchanged shared Medication/Core V4 contracts.

Autocomplete is implemented through module1_intake.api.suggest_medication_names.
ApplicationService.save_manual accepts ManualInputRequest / ManualEditRequest
and uses the common explicit confirmation boundary. UI integration is pending.
"""

STATUS = "PARTIAL"

__all__ = ("STATUS",)
