"""Local development CLI; does not create identities, migrate, or call Modules 2/3."""
import argparse
import os
from uuid import UUID

from .providers import MockProvider, OllamaProvider


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nlp-test", action="store_true", help="Stateless real Ollama extraction testing; no PostgreSQL or dialogue")
    parser.add_argument('--application', action='store_true', help='Frontend-ready MVP services with persisted dialogue and grounded Q&A')
    parser.add_argument('--module2-reference', help='Optional existing read-only Module 2 reference database; never creates/imports data')
    parser.add_argument('--ddi-index', help='Optional existing verified Module 3 official index; never downloads data')
    parser.add_argument("--model", help="Model for --nlp-test (default: NLP_OLLAMA_MODEL or qwen3.5:9b)")
    parser.add_argument("--provider", choices=("mock", "ollama"), help="Dialogue provider (default: mock); --nlp-test uses ollama")
    parser.add_argument("--owner", type=UUID, help="Existing development identity only; required for persisted dialogue")
    parser.add_argument("--workflow", type=UUID, help="Resume an owned persisted workflow")
    parser.add_argument("--reference-build", help="Optional published Core dataset hash for read-only candidate retrieval")
    args = parser.parse_args(argv)
    if args.nlp_test:
        if args.application or args.module2_reference or args.ddi_index:
            parser.error('--nlp-test cannot be combined with application/service options')
        if args.provider == "mock":
            parser.error("--nlp-test uses real Ollama; --provider mock is not supported")
        if args.owner or args.workflow or args.reference_build:
            parser.error("--nlp-test does not accept --owner, --workflow or --reference-build")
        from .interactive import run_extraction_test
        try:
            provider = OllamaProvider(
                args.model or os.environ.get("NLP_OLLAMA_MODEL") or "qwen3.5:9b",
                base_url=os.environ.get("NLP_OLLAMA_URL", "http://127.0.0.1:11434"),
                timeout=float(os.environ.get("NLP_OLLAMA_TIMEOUT", "60")),
            )
        except ValueError:
            parser.error("Invalid Ollama configuration; check model, loopback URL and positive timeout")
        run_extraction_test(provider)
        return
    if args.model and not args.application:
        parser.error("--model is only supported with --nlp-test or --application")
    if (args.module2_reference or args.ddi_index) and not args.application:
        parser.error('Service adapters require --application')
    if args.owner is None:
        parser.error("--owner is required for persisted dialogue")
    dsn = os.environ.get("CORE_DB_DSN")
    if not dsn:
        parser.error("CORE_DB_DSN must point to an already provisioned Core V4 database")
    # Keep the persisted chatbot path separate from stateless extraction.
    import psycopg
    from shared.db import CoreRepository
    from shared.db.identification_adapter import CoreMedicationReference
    from .dialogue import Chatbot

    if args.application and args.provider != 'mock':
        provider = OllamaProvider(args.model or os.environ.get('NLP_OLLAMA_MODEL') or 'qwen3.5:9b',
            base_url=os.environ.get('NLP_OLLAMA_URL', 'http://127.0.0.1:11434'),
            timeout=float(os.environ.get('NLP_OLLAMA_TIMEOUT', '60')))
    else:
        provider = OllamaProvider.from_env() if args.provider == "ollama" else MockProvider()
    with psycopg.connect(dsn, autocommit=True) as connection:
        repo = CoreRepository(connection, authenticated_owner=args.owner)
        reference = CoreMedicationReference(repo, args.reference_build) if args.reference_build else None
        if args.application:
            from .application import ApplicationService
            from .application_cli import run_application
            from .retrieval import Module2FactRetriever
            module2 = None
            try:
                if args.module2_reference:
                    from module2_medications.reference import MedicationReference
                    module2 = MedicationReference(args.module2_reference)
                dataset = None
                if args.ddi_index:
                    from module3_interactions.official_ddinter.dataset import OfficialDataset
                    dataset = OfficialDataset(args.ddi_index)
                service = ApplicationService(repo, provider, reference=reference,
                    medication_retriever=Module2FactRetriever(module2) if module2 else None)
                initial = service.resume(args.workflow) if args.workflow else service.start()
                run_application(service, initial, dataset_build=args.reference_build, dataset=dataset)
            finally:
                if module2:
                    module2.close()
            return
        bot = Chatbot(repo, provider, reference=reference)
        if args.workflow:
            row = repo._owned("workflow_instances", args.workflow)
            identity, revision = row["id"], row["revision"]
            print(f"Resumed {identity} revision={revision} state={row['state']}")
        else:
            reply = bot.start()
            identity, revision = reply.workflow_id, reply.revision
            print(reply.text)
        print("/quit exits; /revise opens correction of completed intake. Type xác nhận to confirm the displayed draft.")
        print(f"workflow={identity} revision={revision}")
        while True:
            try:
                text = input("> ")
            except EOFError:
                break
            if text.strip() == "/quit":
                break
            try:
                reply = bot.revise(identity) if text.strip() == "/revise" else bot.send(identity, text, expected_revision=revision)
                identity, revision = reply.workflow_id, reply.revision
                print(reply.text)
                print(f"workflow={identity} revision={revision} state={reply.state}")
                if reply.handoff:
                    print(reply.handoff.model_dump_json(indent=2))
            except (ValueError, PermissionError, psycopg.Error) as exc:
                print(f"Request rejected ({type(exc).__name__}); reload the owned workflow before retrying.")
                row = repo._owned("workflow_instances", identity)
                revision = row["revision"]


if __name__ == "__main__":
    main()
