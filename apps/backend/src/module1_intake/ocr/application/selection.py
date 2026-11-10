"""Select OCR results without replacing existing evidence."""
from collections import Counter

def extraction_quality(extraction):
    """Structural selection only, not a calibrated accuracy score."""
    if extraction.receipt_items:
        fields = ('product_raw', 'quantity_raw', 'unit_price_raw', 'amount_raw', 'lot_number_raw', 'expiry_date_raw')
        return (len(extraction.receipt_items), sum(item.get(f) is not None for item in extraction.receipt_items for f in fields))
    return (len(extraction.medications), sum(
        sum(getattr(item, f) is not None for f in ('name_raw', 'strength_raw', 'quantity_raw', 'instructions_raw'))
        + sum(a.dose_raw is not None for a in item.administrations) for item in extraction.medications))


def cv_selection_blockers(original, candidate):
    """Do not replace existing literal evidence with changed/missing values."""
    reasons = []
    if original.document_type != candidate.document_type:
        return ['document_type_changed']
    if len(original.medications) != len(candidate.medications) or len(original.receipt_items) != len(candidate.receipt_items):
        return ['item_count_changed']
    def text(value):
        return ' '.join(value.split()) if isinstance(value, str) else value
    for index, (old, new) in enumerate(zip(original.medications, candidate.medications), 1):
        for field in ('name_raw', 'strength_raw', 'ingredient_raw', 'package_size_raw',
                      'route_raw', 'frequency_raw', 'duration_raw', 'quantity_raw', 'instructions_raw'):
            if getattr(old, field) is not None and text(getattr(old, field)) != text(getattr(new, field)):
                reasons.append(f'medication_{index}:{field}_changed_or_missing')
        def schedule(item):
            return Counter((a.timing_normalized or text(a.timing_raw), text(a.dose_raw), text(a.phase_raw))
                           for a in item.administrations)
        if schedule(old) - schedule(new):
            reasons.append(f'medication_{index}:schedule_changed_or_missing')
    for index, (old, new) in enumerate(zip(original.receipt_items, candidate.receipt_items), 1):
        for field in ('group_raw', 'product_raw', 'unit_raw', 'quantity_raw', 'unit_price_raw',
                      'amount_raw', 'lot_number_raw', 'expiry_date_raw'):
            if old.get(field) is not None and text(old.get(field)) != text(new.get(field)):
                reasons.append(f'receipt_{index}:{field}_changed_or_missing')
    return reasons
