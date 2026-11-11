"""Refactor contracts: legacy identity, schema stability and authority boundaries."""
import ast
import hashlib
import importlib
from importlib.util import resolve_name
import json
from pathlib import Path

import pytest

from module1_intake import nlp
from module1_intake.nlp.models import Intent
from module1_intake.nlp.qa_pipeline.composition import GroundedComposer
from module1_intake.nlp.qa_pipeline.contracts import RetrievalQuery, RetrievalResult
from module1_intake.nlp.qa_pipeline.pipeline import HybridQA


ALIASES = {
    'providers': 'understanding.providers', 'routing': 'understanding.routing',
    'validation': 'understanding.validation', 'dialogue': 'dialogue_management.manager',
    'policy': 'dialogue_management.policy', 'fsm': 'dialogue_management.fsm',
    'persistence': 'integration.persistence', 'handoff': 'integration.handoff',
    'qa': 'qa_pipeline.structured', 'retrieval': 'qa_pipeline.structured',
    'hybrid_qa': 'qa_pipeline.pipeline', 'application': 'interfaces.application',
    'application_cli': 'interfaces.application_cli', 'interactive': 'interfaces.interactive',
    '__main__': 'interfaces.cli',
}
PREFIX = 'module1_intake.nlp.'
CHECKPOINT = json.loads(Path(__file__).with_name('nlp_contracts_v2.json').read_text(encoding='utf-8'))


def test_legacy_imports_share_one_implementation_and_preserve_checkpoint_exports(monkeypatch):
    for old, current in ALIASES.items():
        legacy = importlib.import_module(PREFIX + old)
        canonical = importlib.import_module(PREFIX + current)
        assert legacy is canonical, old
    for module, symbols in CHECKPOINT['exports'].items():
        imported = importlib.import_module(PREFIX + module)
        assert all(hasattr(imported, symbol) for symbol in symbols), module
    legacy = importlib.import_module(PREFIX + 'interactive')
    canonical = importlib.import_module(PREFIX + 'interfaces.interactive')
    sentinel = object()
    monkeypatch.setattr(legacy, 'run_extraction_test', sentinel)
    assert canonical.run_extraction_test is sentinel


def test_public_dto_schemas_match_the_working_v2_checkpoint():
    for qualified, expected in CHECKPOINT['schema_sha256'].items():
        module, symbol = qualified.rsplit('.', 1)
        model = getattr(importlib.import_module(PREFIX + module), symbol)
        current = model.model_json_schema()
        if qualified == 'application.ApplicationResponse':
            # Explicitly additive execution-result fields; all pre-existing V2
            # properties and every other public DTO retain their captured schema.
            for field in ('identification_results', 'assessment_id', 'snapshot_id', 'executed_action'):
                current['properties'].pop(field)
        schema = json.dumps(current, sort_keys=True).encode()
        assert hashlib.sha256(schema).hexdigest() == expected, qualified


def test_layer_dependencies_are_acyclic_and_do_not_reenter_compatibility_modules():
    root = Path(nlp.__file__).parent
    files = [root / 'models.py', *(path for folder in ('understanding', 'dialogue_management', 'qa_pipeline', 'integration', 'interfaces')
                                  for path in (root / folder).rglob('*.py') if path.name != '__init__.py')]
    graph = {}
    for path in files:
        module = PREFIX + '.'.join(path.relative_to(root).with_suffix('').parts)
        package = module.rsplit('.', 1)[0]
        dependencies = set()
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.ImportFrom):
                dependencies.add(resolve_name('.' * node.level + (node.module or ''), package) if node.level else node.module)
            elif isinstance(node, ast.Import):
                dependencies.update(alias.name for alias in node.names)
        assert not dependencies.intersection(PREFIX + alias for alias in ALIASES), module
        if module.startswith(PREFIX + 'understanding.'):
            forbidden = ('shared.db', 'psycopg', *(PREFIX + part for part in ('integration', 'dialogue_management', 'qa_pipeline', 'interfaces')))
        elif module == PREFIX + 'qa_pipeline.contracts' or '.qa_pipeline.rag.' in module:
            forbidden = ('shared.db', 'psycopg', *(PREFIX + part for part in ('understanding', 'integration', 'dialogue_management', 'interfaces')))
        elif module == PREFIX + 'qa_pipeline.composition':
            forbidden = ('shared.db', 'psycopg', PREFIX + 'integration', PREFIX + 'interfaces')
        elif module.startswith(PREFIX + 'integration.'):
            forbidden = (PREFIX + 'interfaces', PREFIX + 'qa_pipeline.pipeline')
        else:
            forbidden = ()
        assert not any(dep == limit or dep.startswith(limit + '.') for dep in dependencies for limit in forbidden), module
        graph[module] = dependencies

    def visit(module, active, done):
        assert module not in active, f'Circular dependency: {module}'
        if module not in graph or module in done:
            return
        active.add(module)
        for dependency in graph[module]:
            visit(dependency, active, done)
        active.remove(module)
        done.add(module)

    done = set()
    for module in graph:
        visit(module, set(), done)


def test_missing_structured_evidence_never_calls_qwen_or_future_rag():
    class Forbidden:
        def generate_structured(self, *args):
            pytest.fail('Missing structured evidence must not trigger Qwen composition')

        def retrieve(self, query):
            pytest.fail('Phase A must not search documents')

    class Candidates:
        def retrieve(self, query):
            return RetrievalResult(status='PARTIAL', coverage='REFERENCE_CANDIDATES_ONLY', candidates=[{'id': 'candidate'}])

    qa = HybridQA(composer=GroundedComposer(Forbidden()), documents=Forbidden())
    for intent in (Intent.MEDICATION_QA, Intent.CHECK_INTERACTION):
        answer = qa.answer(intent, RetrievalQuery('Question without evidence', 'general'))
        assert answer.status == 'UNAVAILABLE' and answer.coverage == 'UNASSESSED'
        assert answer.evidence_refs == []
    qa.medication = Candidates()
    answer = qa.answer(Intent.MEDICATION_QA, RetrievalQuery('Question with candidates only', 'general'))
    assert answer.status == 'PARTIAL' and answer.evidence_refs == [] and answer.candidates


def test_rag_interface_remains_disabled_and_uses_the_shared_contract():
    from module1_intake.nlp.qa_pipeline.rag.interface import DisabledDocumentRetriever, RetrievalQuery as Query
    assert Query is RetrievalQuery
    result = DisabledDocumentRetriever().retrieve(Query('future query', 'general'))
    assert result.status == 'UNAVAILABLE' and result.coverage == 'UNASSESSED'
    assert not result.facts and not result.candidates
