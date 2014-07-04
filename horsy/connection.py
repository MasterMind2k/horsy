from __future__ import absolute_import

from django.conf import settings

from .store import DocumentStore
from .search import DocumentSearch

# Create a default document store connection
store = DocumentStore(
  settings.HORSY_MONGODB_SERVERS,
  settings.HORSY_MONGODB_DB
)

# Create a default document search connection
search = DocumentSearch(
  settings.HORSY_ELASTICSEARCH_SERVERS,
  settings.HORSY_ELASTICSEARCH_INDEX
)
