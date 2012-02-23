from __future__ import absolute_import

import datetime
import re
import unicodedata

from ..document import Document, EmbeddedDocument, RESTRICT, CASCADE

class ValidationError(Exception):
  pass

class Field(object):
  """
  Field descriptor (for more information on descriptors see the
  python descriptor protocol).
  """
  creation_counter = 0
  
  def __init__(self, default = None, required = False, revisable = True, virtual = False,
               searchable = True, indexed = False, db_field = None, search_index = None):
    """
    Class constructor.
    """
    self.name = None
    self.db_name = db_field
    
    # Convert the defaulter to a callable lambda function
    if default is not None and not callable(default):
      dvalue = default
      default = lambda: dvalue
    
    self.default = default
    self.required = required
    self.virtual = virtual
    self.searchable = searchable
    self.search_index = search_index or {}
    self.revisable = revisable
    self.indexed = indexed
    
    # Properly setup the creation counter to impose field ordering
    self.creation_counter = Field.creation_counter
    Field.creation_counter += 1
  
  def __get__(self, obj, typ):
    """
    Returns the value of this field.
    """
    value = obj._values.get(self)
    if value is None and self.default is not None:
      obj._values[self] = value = self.default()
    
    return value
  
  def __delete__(self, obj):
    """
    Prevents deletion of this field.
    """
    raise AttributeError("You cannot remove fields from a document!")
  
  def __set__(self, obj, value):
    """
    Sets the value for this field.
    """
    obj._values[self] = value
  
  def contribute_to_class(self, cls, name):
    """
    Installs this field into some document.
    """
    if hasattr(cls, name):
      raise AttributeError("Field name conflict for '{0}/{1}'!".format(cls.__name__, name))
    
    self.name = name
    if self.db_name is None:
      # TODO generate db_name
      self.db_name = name
    
    self.cls = cls
    self.prepare()
    cls._meta.add_field(self)
    setattr(cls, name, self)
  
  def prepare(self):
    """
    Called when constructing the parent class, when name and class are
    already known.
    """
    pass
  
  def check_configuration(self):
    """
    Called after all fields on the document have been prepared to enable the
    field to check its configuration and raise configuration errors.
    """
    pass
  
  def validate(self, value, document):
    """
    Validates this field.
    """
    pass
  
  def _validate(self, value, document):
    """
    Validates this field.
    """
    if value is None and self.required:
      raise ValidationError("Field '{0}' is required!".format(self.name))
    
    if value is not None:
      self.validate(value, document)
  
  def pre_save(self, value, document):
    """
    Called before saving the field and should return the field's value.
    """
    if value is None and self.default is not None:
      return self.default()
    
    return value
  
  def post_save(self, value, document):
    """
    Called after the field has been saved into the database.
    """
    pass
  
  def from_store(self, value, document):
    """
    Converts value from MongoDB store.
    """
    return value
  
  def from_search(self, value, document):
    """
    Converts value from Elastic Search.
    """
    return None
  
  def to_store(self, value, document):
    """
    Converts value to MongoDB store.
    """
    return value
  
  def to_search(self, value, document):
    """
    Converts value to Elastic Search.
    """
    return None
  
  def to_revision(self, value, document):
    """
    Converts value so that it is suitable for inclusion into a document
    revision.
    """
    return value
  
  def from_revision(self, value, document):
    """
    Converts value from a document revision into a rollback-ed document.
    """
    return value
  
  def get_indices(self):
    """
    This method may return a dictionary of indices for this field. Keys
    indicate subfields (for nested documents), to index the field itself
    use '.' as a key name. Dictionary values represent sort order.
    """
    if self.indexed:
      return { "." : Document.ASCENDING }
    else:
      return {}

  def get_subfield_metadata(self):
    """
    If this field has any subfields that have type metadata in the form
    of Field instances, it should be returned here.
    """
    return None

  def get_search_mapping(self):
    """
    This method may return a dictionary describing the mapping for
    Elastic Search.
    """
    return dict(
      boost = self.search_index.get("boost", 1.0),
      store = "no",
    )

  def setup_reverse_references(self, document_class, field_name):
    """
    This method may recursively setup reverse references.
    """
    pass

class PrimaryKeyField(Field):
  """
  Primary key field.
  """
  def __init__(self, db_field = '_id', **kwargs):
    kwargs['virtual'] = True
    kwargs['searchable'] = False
    super(PrimaryKeyField, self).__init__(db_field = db_field, **kwargs)

class TextField(Field):
  """
  A simple text field.
  """
  def __init__(self, **kwargs):
    super(TextField, self).__init__(**kwargs)
  
  def from_store(self, value, document):
    return unicode(value)
  
  from_search = from_store
  to_store = from_store
  to_search = from_store

  def get_search_mapping(self):
    """
    Returns field mapping for Elastic Search.
    """
    mapping = super(TextField, self).get_search_mapping()
    mapping.update(dict(
      type = "string",
      index = "analyzed" if self.search_index.get("analyzed", True) else "not_analyzed",
    ))

    if self.search_index.get("analyzer", None) is not None:
      mapping["analyzer"] = self.search_index["analyzer"]

    if self.search_index.get("search_analyzer", None) is not None:
      mapping["search_analyzer"] = self.search_index["search_analyzer"]

    return mapping

class IntegerField(Field):
  """
  A simple integer field.
  """
  def __init__(self, min_value = None, max_value = None, **kwargs):
    """
    Class constructor.
    """
    self.min_value = min_value
    self.max_value = max_value
    super(IntegerField, self).__init__(**kwargs)
  
  def validate(self, value, document):
    """
    Validates this field.
    """
    value = int(value)
    if self.min_value is not None and value < self.min_value:
      raise ValidationError("Minimum allowed value for '{0}' is '{1}'!".format(self.name, self.min_value))
    
    if self.max_value is not None and value > self.max_value:
      raise ValidationError("Maximum allowed value for '{0}' is '{1}'!".format(self.name, self.max_value))
  
  def from_store(self, value, document):
    """
    Converts value from MongoDB store.
    """
    return int(value)
  
  to_store = from_store
  from_search = from_store
  to_search = from_store

  def get_search_mapping(self):
    """
    Returns field mapping for Elastic Search.
    """
    mapping = super(IntegerField, self).get_search_mapping()
    mapping.update(dict(
      type = "integer",
    ))
    return mapping

class FloatField(Field):
  """
  A simple float field.
  """
  def __init__(self, min_value = None, max_value = None, **kwargs):
    """
    Class constructor.
    """
    self.min_value = min_value
    self.max_value = max_value
    super(FloatField, self).__init__(**kwargs)
  
  def validate(self, value, document):
    """
    Validates this field.
    """
    value = float(value)
    if self.min_value is not None and value < self.min_value:
      raise ValidationError("Minimum allowed value for '{0}' is '{1}'!".format(self.name, self.min_value))
    
    if self.max_value is not None and value > self.max_value:
      raise ValidationError("Maximum allowed value for '{0}' is '{1}'!".format(self.name, self.max_value))
  
  def from_store(self, value, document):
    """
    Converts value from MongoDB store.
    """
    return float(value)
  
  to_store = from_store
  from_search = from_store
  to_search = from_store

  def get_search_mapping(self):
    """
    Returns field mapping for Elastic Search.
    """
    mapping = super(FloatField, self).get_search_mapping()
    mapping.update(dict(
      type = "float",
    ))
    return mapping

class BooleanField(Field):
  """
  A simple boolean field.
  """
  def __init__(self, **kwargs):
    """
    Class constructor.
    """
    super(BooleanField, self).__init__(**kwargs)
  
  def from_store(self, value, document):
    """
    Converts value from MongoDB store.
    """
    return bool(value)
  
  from_search = from_store
  to_store = from_store
  to_search = from_store

  def get_search_mapping(self):
    """
    Returns field mapping for Elastic Search.
    """
    mapping = super(BooleanField, self).get_search_mapping()
    mapping.update(dict(
      type = "boolean",
    ))
    return mapping

class YearField(IntegerField):
  """
  A simple year field.
  """
  def __init__(self, **kwargs):
    """
    Class constructor.
    """
    kwargs['min_value'] = 1000
    kwargs['max_value'] = 3000
    super(YearField, self).__init__(**kwargs)

class MonthField(IntegerField):
  """
  A simple month field.
  """
  def __init__(self, **kwargs):
    """
    Class constructor.
    """
    kwargs['min_value'] = 1
    kwargs['max_value'] = 12
    super(MonthField, self).__init__(**kwargs)

class DayField(IntegerField):
  """
  A simple day field.
  """
  def __init__(self, validate_against = None, **kwargs):
    """
    Class constructor.
    """
    if validate_against is not None:
      self.validate_month, self.validate_year = validate_against
    else:
      self.validate_month, self.validate_year = None, None
    
    kwargs['min_value'] = 1
    kwargs['max_value'] = 31
    super(DayField, self).__init__(**kwargs)
  
  def validate(self, value, document):
    """
    Validates this field.
    """
    # Perform basic validation
    super(DayField, self).validate(value, document)
    
    # Perform year-month-dependent validation
    if self.validate_month is not None:
      try:
        datetime.date(
          getattr(document, self.validate_year),
          getattr(document, self.validate_month),
          value
        )
      except (AttributeError, ValueError):
        raise ValidationError("Invalid day for field '{0}' when validated against month and year!".format(self.name))

class DateTimeField(Field):
  """
  Date and time combined field.
  """
  def __init__(self, auto_update = False, **kwargs):
    """
    Class constructor.
    """
    super(DateTimeField, self).__init__(**kwargs)
    self.auto_update = auto_update
  
  def pre_save(self, value, document):
    """
    Sets up a default value when auto update is set for this field.
    """
    if self.auto_update:
      value = datetime.datetime.utcnow()
    
    return super(DateTimeField, self).pre_save(value, document)
  
  def validate(self, value, document):
    """
    Validates this field.
    """
    if not isinstance(value, datetime.datetime):
      raise ValidationError("Not a valid date/time value for field '{0}', need datetime instance!".format(self.name))

  def get_search_mapping(self):
    """
    Returns field mapping for Elastic Search.
    """
    mapping = super(DateTimeField, self).get_search_mapping()
    mapping.update(dict(
      type = "date",
    ))
    return mapping

class SlugField(TextField):
  """
  Slug field that can be generated by composing other fields.
  """
  def __init__(self, template, **kwargs):
    """
    Class constructor.
    """
    self.template = template
    super(SlugField, self).__init__(**kwargs)
  
  def pre_save(self, value, document):
    """
    Automatically generates the slug.
    """
    variables = { 'self' : document }
    if isinstance(document, EmbeddedDocument):
      variables['parent'] = document._parent
    
    value = unicode(self.template).format(**variables)
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    return re.sub('[-\s]+', '-', value)

class EnumField(TextField):
  """
  Field that may contain one of the many predefined values.
  """
  # A list of all EnumTypes in the application, used for compiling a javascript catalog.
  enum_types_list = set()

  def __init__(self, choices, enum_type = None, **kwargs):
    """
    Class constructor.
    """
    self.enum_type = enum_type
    self.choices = {}
    self.localized = {}
    for key, value in choices.iteritems():
      try:
        value, localized = value
        self.localized[value] = localized
      except ValueError:
        pass
      
      self.choices[value] = key
    
    super(TextField, self).__init__(**kwargs)
  
  def prepare(self):
    """
    Called when constructing the parent class, when name and class are
    already known.
    """
    class EnumType:
      localized_choices = []
    
    for key, value in self.choices.iteritems():
      setattr(EnumType, value, key)
    
    for key, value in self.localized.iteritems():
      EnumType.localized_choices.append((key, value))
    
    if self.enum_type is None:
      enum_type = self.name.capitalize()
    else:
      enum_type = self.enum_type
    setattr(self.cls, enum_type, EnumType)
    EnumField.enum_types_list.add('{0}.{1}.{2}'.format(str(self.cls.__module__), self.cls.__name__, enum_type))
  
  def validate(self, value, document):
    """
    Validates this field.
    """
    if value not in self.choices:
      raise ValidationError("Invalid value '{1}' for enumeration field '{0}'!".format(self.name, value))

  def get_search_mapping(self):
    """
    Returns field mapping for Elastic Search.
    """
    mapping = super(EnumField, self).get_search_mapping()
    mapping.update(dict(
      index = "not_analyzed",
    ))
    return mapping

class EmbeddedDocumentField(Field):
  """
  Field containing an embedded document.
  """
  def __init__(self, embedded, **kwargs):
    """
    Class constructor.
    
    @param embedded: Embedded document class
    """
    if not issubclass(embedded, EmbeddedDocument):
      raise TypeError("Document parameter must be a subclass of EmbeddedDocument!")
    
    self.embedded = embedded
    super(EmbeddedDocumentField, self).__init__(**kwargs)
  
  def get_indices(self):
    """
    This method may return a dictionary of indices for this field. Keys
    indicate subfields (for nested documents), to index the field itself
    use '.' as a key name. Dictionary values represent sort order.
    """
    indices = {}
    for name, subfield in self.embedded._meta.fields.iteritems():
      for ifield, order in subfield.get_indices().iteritems():
        if ifield == '.':
          indices[subfield.db_name] = order
        else:
          indices['{0}.{1}'.format(subfield.db_name, ifield)] = order
    
    return indices

  def get_subfield_metadata(self):
    """
    If this field has any subfields that have type metadata in the form
    of Field instances, it should be returned here.
    """
    return self.embedded._meta

  def setup_reverse_references(self, document_class, field_name):
    """
    This method may recursively setup reverse references.
    """
    for name, subfield in self.embedded._meta.fields.iteritems():
      subfield.setup_reverse_references(document_class, '{0}.{1}'.format(field_name, name))
  
  def __set__(self, obj, value):
    """
    Sets the value for this field.
    """
    super(EmbeddedDocumentField, self).__set__(obj, value)
    if value is not None:
      value._parent = obj
  
  def from_store(self, value, document):
    """
    Converts value from MongoDB store.
    """
    doc = self.embedded()
    doc._parent = document
    doc._set_from_db(value)
    return doc
  
  def to_store(self, value, document):
    """
    Converts value to MongoDB store.
    """
    if not isinstance(value, self.embedded):
      raise ValueError("Embedded document must be an instance of '{0}'!".format(self.embedded.__name__))
    
    value._parent = document
    return value._db_prepare()
  
  def post_save(self, value, document):
    """
    Called after the field has been saved into the database. This is only
    called if the field has been modified.
    """
    value._db_post_save()
  
  def from_search(self, value, document):
    """
    Converts value from Elastic Search.
    """
    doc = self.embedded()
    doc._parent = document
    doc._set_from_search(value)
    return doc
  
  def to_search(self, value, document):
    """
    Converts value to Elastic Search store.
    """
    if not isinstance(value, self.embedded):
      raise ValueError("Embedded document must be an instance of '{0}'!".format(self.embedded.__name__))
    
    value._parent = document
    return value._search_prepare()

  def get_search_mapping(self):
    """
    Returns field mapping for Elastic Search.
    """
    mapping = super(EmbeddedDocumentField, self).get_search_mapping()
    mapping.update(dict(
      type = "object",
      dynamic = "strict",
      enabled = self.searchable,
      properties = self.embedded._meta.search_mapping_prepare()
    ))
    return mapping

class ListField(Field):
  """
  Field containing a list of other fields.
  """
  def __init__(self, field, **kwargs):
    """
    Class constructor.
    
    @param field: Field instance for list elements
    """
    if not isinstance(field, Field):
      raise TypeError("Field parameter must be a valid field!")
    
    if 'default' not in kwargs:
      kwargs['default'] = lambda: []
    
    self.subfield = field
    super(ListField, self).__init__(**kwargs)
  
  def prepare(self):
    """
    Called when constructing the parent class, when name and class are
    already known.
    """
    self.subfield.name = self.name
    self.subfield.cls = self.cls
    self.subfield.prepare()
  
  def setup_reverse_references(self, document_class, field_name):
    """
    This method may recursively setup reverse references.
    """
    self.subfield.setup_reverse_references(document_class, field_name)
  
  def validate(self, value, document):
    """
    Validates this field.
    """
    for element in value:
      self.subfield.validate(element, document)
  
  def get_indices(self):
    """
    This method may return a dictionary of indices for this field. Keys
    indicate subfields (for nested documents), to index the field itself
    use '.' as a key name. Dictionary values represent sort order.
    """
    return self.subfield.get_indices()
  
  def from_store(self, value, document):
    """
    Converts value from MongoDB store.
    """
    return [self.subfield.from_store(e, document) for e in value]
  
  def to_store(self, value, document):
    """
    Converts value to MongoDB store.
    """
    return [self.subfield.to_store(e, document) for e in value]
  
  def from_search(self, value, document):
    """
    Converts value from Elastic Search store.
    """
    return [self.subfield.from_search(e, document) for e in value]
  
  def to_search(self, value, document):
    """
    Converts value to Elastic Search store.
    """
    return [self.subfield.to_search(e, document) for e in value]
  
  def post_save(self, value, document):
    """
    Called after the field has been saved into the database. This is only
    called if the field has been modified.
    """
    for element in value:
      self.subfield.post_save(element, document)

  def get_search_mapping(self):
    """
    Returns field mapping for Elastic Search.
    """
    return self.subfield.get_search_mapping()

class SetField(ListField):
  """
  Field containing a set of other fields.
  """
  def __init__(self, *args, **kwargs):
    """
    Class constructor.
    """
    if 'default' not in kwargs:
      kwargs['default'] = lambda: set()
    
    super(SetField, self).__init__(*args, **kwargs)
  
  def from_store(self, value, document):
    """
    Converts value from MongoDB store.
    """
    return set(super(SetField, self).from_store(value, document))
  
  def to_store(self, value, document):
    """
    Converts value to MongoDB store.
    """
    return list(set(super(SetField, self).to_store(value, document)))
  
  def from_search(self, value, document):
    """
    Converts value from Elastic Search store.
    """
    return set(super(SetField, self).from_search(value, document))
  
  def to_search(self, value, document):
    """
    Converts value to Elastic Search store.
    """
    return list(set(super(SetField, self).to_search(value, document)))

class SearchCompositeField(Field):
  """
  Field that enables composition of other fields into text strings for
  purpuses of search persistance.
  """
  def __init__(self, composition, **kwargs):
    """
    Class constructor.
    """
    self.composition = composition
    kwargs['virtual'] = True
    kwargs['revisable'] = False
    kwargs['searchable'] = True
    super(SearchCompositeField, self).__init__(**kwargs)
  
  def from_search(self, value, document):
    """
    Converts value from Elastic Search store.
    """
    return value
  
  def __get__(self, obj, typ):
    """
    Override descriptor's get method to always return a precomposed value.
    """
    return self.composition.format(**{ 'self' : obj })
  
  def to_search(self, value, document):
    """
    Converts value to Elastic Search store.
    """
    return self.composition.format(**{ 'self' : document })

  def get_search_mapping(self):
    """
    Returns field mapping for Elastic Search.
    """
    mapping = super(SearchCompositeField, self).get_search_mapping()
    mapping.update(dict(
      type = "string",
      index = "analyzed" if self.search_index.get("analyzed", True) else "not_analyzed",
    ))

    if self.search_index.get("analyzer", None) is not None:
      mapping["analyzer"] = self.search_index["analyzer"]

    if self.search_index.get("search_analyzer", None) is not None:
      mapping["search_analyzer"] = self.search_index["search_analyzer"]

    return mapping

class DictField(Field):
  """
  Similar to an embedded field but without type checks, allowing any
  serializable structure.
  """
  def __init__(self, **kwargs):
    """
    Class constructor.
    """
    if "default" not in kwargs:
      kwargs["default"] = lambda: {}
    super(DictField, self).__init__(**kwargs)

  def from_store(self, value, document):
    """
    Converts value from MongoDB store.
    """
    return dict(value)

  to_store = from_store
  from_search = from_store
  to_search = from_store

  def get_search_mapping(self):
    """
    Returns field mapping for Elastic Search.
    """
    mapping = super(DictField, self).get_search_mapping()
    mapping.update(dict(
      type = "object",
      dynamic = True,
      enabled = self.searchable,
    ))
    return mapping
