from django.core.management import base as management_base

from ... import registry as horsy_registry

class Command(management_base.BaseCommand):
  help = "Performs a search type mapping synchronization."
  requires_model_validation = True

  def handle(self, *args, **options):
    """
    Performs a search type mapping synchronization.
    """
    for document_cls in horsy_registry.document_registry:
      if document_cls._meta.searchable:
        self.stdout.write("Syncing search type mapping for %s...\n" % document_cls.__name__)
        document_cls._meta.emit_search_mappings()
