"""Persist the source OCR's literal output through the unchanged Core V4 review."""
from copy import deepcopy
import hashlib
from pathlib import Path

from shared.db.intake_adapter import medication_fields, persist_module1
from shared.intake_contracts import Medication, Administration

ROOT = Path(__file__).resolve().parents[4]


def core_medications(response):
    parsed = response.extraction_run.raw_output['parsed']
    result = []
    for row in parsed['medications']:
        values = {key: deepcopy(row[key]) for key in Medication.model_fields
                  if key in row and key not in {'administrations', 'evidence_text'}}
        values['evidence_text'] = row.get('evidence_text') or row.get('product_raw') or response.extraction_run.raw_output['ocr']['text']
        values['administrations'] = [Administration(timing_raw=a.get('timing_raw'), dose_raw=a.get('dose_raw'))
                                    for a in row.get('administrations', [])]
        result.append(Medication(**values))
    return result


def preview(app, workflow_id, revision, image_path, *, region=None):
    from .service import LocalOcrService

    with app.bot.store.turn(workflow_id):
        workflow = app.bot._check(workflow_id, revision)
        if workflow['state'] in {'COMPLETED', 'CANCELLED', 'FAILED'} or workflow['context'].get('voice_draft'):
            raise ValueError('Use an active workflow without a pending voice draft')
        response = LocalOcrService().extract(image_path, region=region)
        meds = core_medications(response)
        if not meds:
            return {'ocr': response.model_dump(mode='json'), 'review': app.resume(workflow_id).model_dump(mode='json')}
        # The source engine actually retains this object before returning. Resolve
        # the canonical run path ourselves; never accept a locator from the client.
        retained = (ROOT / 'data/local/module1/runs' / str(response.extraction_run.extraction_run_id) /
                    ('original' + Path(image_path).suffix.lower())).resolve()
        assert retained.is_relative_to(ROOT / 'data/local/module1/runs')
        original_bytes = retained.read_bytes()
        raw = response.extraction_run.raw_output
        payload = {'schema': 'input.v4', 'digest_basis': 'ORIGINAL_BYTES', 'input_source': 'OCR',
            'text': raw['ocr'].get('text', ''), 'object_locator': {'uri': retained.as_uri(),
                'sha256': hashlib.sha256(original_bytes).hexdigest()}}
        message = app.repo.append_message(workflow['conversation_id'], 'USER', payload['text'],
            {'schema': 'message.v4', 'content_refs': [{'kind': 'IMAGE', 'locator': payload['object_locator'],
                'artifact_sha256': payload['object_locator']['sha256']}], 'input_source': 'OCR'})
        extraction = {'schema': 'extraction.v4', 'medications': [medication_fields(m.model_dump()) for m in meds],
            'document_instructions_raw': raw['parsed'].get('document_instructions_raw', []),
            'warnings': raw['parsed'].get('warnings', []), 'ocr_source_output': raw}
        saved = persist_module1(app.repo, workflow['intake_session_id'], original_bytes, extraction,
            modality='IMAGE', input_payload=payload, extractor_name=response.extraction_run.engine_name,
            extractor_version=response.extraction_run.engine_version or 'source-e41a745',
            content_type='image/' + ('jpeg' if retained.suffix in {'.jpg', '.jpeg'} else retained.suffix[1:]), message=message['id'])
        rows = app.bot.store.entries(workflow) + saved['entries']
        ctx = deepcopy(workflow['context'])
        ctx.update(entry_version_ids=[str(row['id']) for row in rows], pending_confirmation=None,
                   awaiting_purpose=False, active_intents=['ADD_MEDICATION'], dialogue_act='PROVIDE_INFO', qa_results=[])
        ctx.pop('error_code', None)
        review = app._response(app.bot._intake_progress(workflow, ctx, rows))
        return {'ocr': response.model_dump(mode='json'), 'review': review.model_dump(mode='json')}


def edit(app, workflow_id, revision, entry_version_id, medication):
    with app.bot.store.turn(workflow_id):
        workflow = app.bot._check(workflow_id, revision)
        if workflow['state'] in {'COMPLETED', 'CANCELLED', 'FAILED'} or workflow['context'].get('voice_draft'):
            raise ValueError('OCR review requires an active workflow without a voice draft')
        rows = app.bot.store.entries(workflow)
        matches = [n for n, row in enumerate(rows) if str(row['id']) == str(entry_version_id)]
        if len(matches) != 1:
            raise PermissionError('Entry is outside the current owned OCR review')
        index = matches[0]
        prior = rows[index]
        app.bot.store.assert_latest(prior)
        if prior['confirmed_at'] is not None:
            raise ValueError('Create an explicit correction workflow before changing confirmed OCR')
        item = app.repo._owned('intake_items', prior['item_id'])
        original = app.repo._owned('intake_extractions', item['extraction_id'])
        inp = app.repo._owned('intake_inputs', original['input_id'])
        if inp['modality'] != 'IMAGE' or inp['payload_or_locator'].get('input_source') != 'OCR':
            raise ValueError('Entry was not created from a retained OCR image')
        result = {'schema': 'extraction.v4', 'medications': [medication_fields(medication.model_dump())],
            'warnings': [], 'document_instructions_raw': [], 'original_ocr_extraction_id': str(original['id']),
            'user_reviewed_fields': medication.model_dump(mode='json')}
        attempt = app.repo.record_extraction(inp['id'], 'ocr-user-review', 'core-v4', result)
        rows[index] = app.repo.correct_entry(prior['id'], medication_fields(medication.model_dump()),
                                            source_extraction=attempt['id'])
        app.repo.append_message(workflow['conversation_id'], 'USER', medication.model_dump_json(),
            {'schema': 'message.v4', 'content_refs': [], 'input_source': 'OCR_REVIEW'})
        ctx = deepcopy(workflow['context'])
        ctx.update(entry_version_ids=[str(row['id']) for row in rows], pending_confirmation=None,
                   active_intents=['ADD_MEDICATION'], dialogue_act='CORRECT', qa_results=[])
        return app._response(app.bot._intake_progress(workflow, ctx, rows))
