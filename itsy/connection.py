from __future__ import absolute_import

from django.conf import settings

from .store import DocumentStore
from .search import DocumentSearch

# Create a default document store connection
store = DocumentStore(
  settings.ITSY_MONGODB_SERVERS,
  settings.ITSY_MONGODB_DB
)

# Create a default document search connection
search = DocumentSearch(
  settings.ITSY_ELASTICSEARCH_SERVERS,
  settings.ITSY_ELASTICSEARCH_INDEX
)
