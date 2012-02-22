import optparse

from django.core.management import base as management_base
from django.utils import importlib

from ... import document as itsy_document
from ... import tasks as itsy_tasks

class Command(management_base.BaseCommand):
  args = "class_path"
  help = "Performs a reindex of the given document class."
  requires_model_validation = True
  option_list = management_base.BaseCommand.option_list + (
    optparse.make_option('--background', action = 'store_true', dest = 'background', default = False,
      help = "Should the reindexing be performed by background workers."),

    optparse.make_option('--recreate-index', action = 'store_true', dest = 'recreate-index', default = False,
      help = "Should the index be dropped and recreated. THIS WILL ERASE ALL DATA!")
  )

  def handle(self, *args, **options):
    """
    Performs a reindex of the given document class.
    """
    if len(args) != 1:
      raise management_base.CommandError("Reindex command takes exactly one argument!")

    # Load the specified document class
    class_path = args[0]
    module_name = class_path[:class_path.rfind(".")]
    class_name = class_path[class_path.rfind(".") + 1:]
    module = importlib.import_module(module_name)
    document_class = getattr(module, class_name)

    if not issubclass(document_class, itsy_document.Document):
      raise management_base.CommandError("Specified class is not a valid Document!")

    if options.get("recreate-index"):
      # Drop the index and recreate it
      self.stdout.write("Recreating index...\n")
      document_class._meta.search_engine.drop()
      document_class._meta.emit_search_mappings()

    if options.get("background"):
      # Spawn the reindex task
      itsy_tasks.search_index_reindex.delay(document_class)

      # Notify the user that the reindex has started in the background
      self.stdout.write("Reindex of %s has been initiated in the background.\n" % class_path)
    else:
      self.stdout.write("Performing foreground reindex of %s...\n" % class_path)
      itsy_tasks.search_index_reindex(document_class)
