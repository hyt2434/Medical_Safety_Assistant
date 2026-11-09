"""Terminal presentation for stateless extraction through the existing NLP pipeline."""
import json

from .models import Medication, Understanding
from .providers import InferenceCategory as C, InferenceError, Provider, understand


RAW_SLOTS = tuple(name for name in Medication.model_fields if name.endswith('_raw'))
FAILURE_HELP = {
    C.CONNECTIVITY: 'Cannot reach the local Ollama server.',
    C.TIMEOUT: 'Ollama request timed out.',
    C.HTTP_STATUS: 'Ollama returned an unsuccessful HTTP status; check the server and installed model.',
    C.HTTP_RESPONSE: 'Ollama returned an invalid response envelope.',
    C.INCOMPLETE_RESPONSE: 'Ollama did not complete the answer; truncated output was rejected.',
    C.EMPTY_RESPONSE: 'Ollama returned no structured answer.',
    C.RESPONSE_SIZE: 'Structured output exceeded the accepted size.',
    C.JSON: 'The answer was not valid JSON.',
    C.SCHEMA: 'The answer did not match the strict Pydantic schema.',
    C.EVIDENCE: 'Source spans or medication slot roles failed strict evidence validation.',
    C.PROVIDER: 'The inference provider failed.',
}


def shown(value) -> str:
    # Preserve Vietnamese while escaping controls, newlines and terminal escapes.
    return json.dumps(value, ensure_ascii=False)


def format_understanding(value: Understanding) -> str:
    lines = ['Validation: PASSED (JSON, schema, source evidence)', 'Validation errors: none',
             f'Ambiguous: {"yes" if value.ambiguous else "no"}', f'Dialogue act: {value.dialogue_act.value}', f'Intents: {len(value.intents)}']
    for intent in value.intents:
        lines.append(f'  - {intent.intent.value}; evidence: {shown(intent.evidence_text)}')
        if intent.intent.value == 'ADD_MEDICATION':
            lines.append(f'    record_request_raw: {shown(intent.record_request_raw)} (no save/confirmation authorization)')
    if not value.intents:
        lines.append('  (none extracted)')
    lines.append(f'Medications: {len(value.medications)}')
    for index, med in enumerate(value.medications, 1):
        lines.append(f'  Medication {index}')
        lines.append(f'    evidence_text: {shown(med.evidence_text)}')
        for slot in RAW_SLOTS:
            lines.append(f'    {slot}: {shown(getattr(med, slot))}')
        lines.append(f'    administrations: {len(med.administrations)}')
        for number, admin in enumerate(med.administrations, 1):
            lines.append(f'      {number}. timing_raw: {shown(admin.timing_raw)}; dose_raw: {shown(admin.dose_raw)}')
            lines.append(f'         timing_slots_raw: {shown(admin.timing_slots_raw)}')
        missing = [slot for slot in RAW_SLOTS if slot not in {'negation_raw', 'uncertainty_raw'}
                   and getattr(med, slot) is None]
        if not any(admin.timing_raw for admin in med.administrations):
            missing.append('administrations.timing_raw')
        lines.append(f'    Missing/unreported data slots: {", ".join(missing) or "none"}')
        lines.append(f'    Uncertain fields (reported/marked): {", ".join(med.uncertain_fields) or "none"}')
    if not value.medications:
        lines.append('  (none extracted)')
    lines.append('Null/missing means not stated, not a required-field or medication safety assessment.')
    return '\n'.join(lines)


def format_failure(error: InferenceError) -> str:
    lines = ['Extraction/validation: FAILED', f'  {error.category.value}: {FAILURE_HELP[error.category]}']
    for diagnostic in error.diagnostics:
        status = f'; HTTP {diagnostic.http_status}' if diagnostic.http_status is not None else ''
        lines.append(f'  Attempt {diagnostic.attempt}: {diagnostic.category.value}{status}')
    lines.append('No extraction accepted. Raw model output and exception details are hidden.')
    return '\n'.join(lines)


def run_extraction_test(provider: Provider, *, read=input, write=print) -> None:
    write('STATELESS NLP EXTRACTION TEST - real Ollama')
    write(f'Model: {shown(getattr(provider, "model", provider.name))}')
    write('Each input is independent. No dialogue, confirmation, persistence or medication safety assessment.')
    write('Validated source text is displayed locally. Prefer synthetic examples. Type /exit to quit.')
    try:
        while True:
            text = read('nlp> ')
            if text.strip().casefold() == '/exit':
                break
            if not text.strip():
                write('Enter a Vietnamese medication sentence, or /exit.')
                continue
            if len(text) > 12000:
                write('Input rejected: maximum 12000 characters.')
                continue
            try:
                value = understand(provider, text, {})
            except InferenceError as error:
                write(format_failure(error))
            else:
                write(format_understanding(value))
    except (EOFError, KeyboardInterrupt):
        pass
    write('Extraction test ended.')
