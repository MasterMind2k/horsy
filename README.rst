=====
Horsy
=====

Horsy, an Itsy fork, MongoDB Document-Object Mapper with integrated Elastic Search support.

This project has been forked to continue development for usage in Podnapisi.NET and OMDb.si sites.

===========
Quick usage
===========

.. code-block:: python

  import horsy
  import pyes

  # A document class
  class Person(horsy.Document):
    class SubDocument(horsy.EmbeddedDocument):
      field = horsy.IntegerField()
      second_field = horsy.FloatField()

    first_name = horsy.TextField()
    last_name = horsy.TextField()
    birth_date = horsy.DateField()
    comments = horsy.ListField(horsy.DictField(), searchable = False)
    a_subdocument = horsy.EmbeddedDocumentField(SubDocument, searchable = False)

    class Meta:
      index_fields = ['first_name', 'last_name']
      collection = 'something.people'

  # Create, modify same as with Django ORM
  person = Person(first_name = 'first_name',
                  last_name  = 'last_name')
  person.save()

  # Elastic search
  import pyes
  q = pyes.BoolQuery()
  q.add_must(pyes.TextQuery('first_name', 'first_name'))
  q.add_must(pyes.WildcardQuery('last_name', '*_name'))
  results = Person.find_es(q).order_by('last_name', 'first_name')
