from django.core.exceptions import ImproperlyConfigured
from django.utils.copycompat import deepcopy
from tastypie.fields import ApiField


class DeclarativeMetaclass(type):
    def __new__(cls, name, bases, attrs):
        attrs['base_fields'] = {}
        
        # Inherit any fields from parent(s).
        try:
            parents = [b for b in bases if issubclass(b, Representation)]
            
            for p in parents:
                fields = getattr(p, 'base_fields', None)
                
                if fields:
                    attrs['base_fields'].update(fields)
        except NameError:
            pass
        
        for field_name, obj in attrs.items():
            if isinstance(obj, ApiField):
                field = attrs.pop(field_name)
                field.instance_name = field_name
                attrs['base_fields'][field_name] = field
        
        new_class = super(DeclarativeMetaclass, cls).__new__(cls, name, bases, attrs)
        new_class._meta = getattr(new_class, 'Meta', None)
        
        if not new_class._meta:
            raise ImproperlyConfigured("An inner Meta class is required to configure %s." % repr(new_class))
        
        return new_class


class Representation(object):
    """
    By default, handles the CRUD operations for a single object.
    
    Should be pure data (fields + data object).
    """
    __metaclass__ = DeclarativeMetaclass
    
    def __init__(self, *args, **kwargs):
        self.object_class = getattr(self._meta, 'object_class', None)
        self.instance = None
        
        # Use a copy of the field instances, not the ones actually stored on
        # the class.
        self.fields = deepcopy(self.base_fields)
        
        # Now that we have fields, populate fields via kwargs if found.
        for key, value in kwargs.items():
            if key in self.fields:
                self.fields[key].value = value
        
        if self.object_class is None:
            raise ImproperlyConfigured("Using the Representation requires providing an object_class in the inner Meta class.")
    
    def __getattr__(self, name):
        if name in self.fields:
            return self.fields[name]
    
    @classmethod
    def get_list(cls, **kwargs):
        raise NotImplementedError
    
    def get(self, **kwargs):
        raise NotImplementedError
    
    def create(self):
        raise NotImplementedError
    
    def update(self, **kwargs):
        raise NotImplementedError
    
    def delete(self):
        raise NotImplementedError
    
    def get_resource_uri(self):
        """
        This needs to be implemented at the user level.
        
        A ``return reverse("api_%s_detail" % object_name, kwargs={'obj_id': object.id})``
        should be all that would be needed.
        """
        raise NotImplementedError
    
    def full_dehydrate(self, obj):
        """
        Given an object instance, extract the information from it to populate
        the representation.
        """
        # Dehydrate each field.
        for field_name, field_object in self.fields.items():
            field_object.value = field_object.dehydrate(obj)
        
        # Run through optional overrides.
        for field_name, field_object in self.fields.items():
            method = getattr(self, "dehydrate_%s" % field_name, None)
            
            if method:
                field_object.value = method(obj)
        
        self.dehydrate(obj)
    
    def dehydrate(self, obj):
        pass
    
    def full_hydrate(self):
        """
        Given a populated representation, distill it and turn it back into
        a full-fledged object instance.
        """
        if self.instance is None:
            self.instance = self.object_class()
        
        for field_name, field_object in self.fields.items():
            if field_object.attribute:
                value = field_object.hydrate()
                
                if value is not None:
                    setattr(self.instance, field_object.attribute, value)
        
        for field_name, field_object in self.fields.items():
            method = getattr(self, "hydrate_%s" % field_name, None)
            
            if method:
                method()
        
        self.hydrate()
    
    def hydrate(self):
        pass
    
    def to_dict(self):
        data = {}
        
        for field_name, field_object in self.fields.items():
            data[field_name] = field_object.value
        
        return data
    
    class Meta:
        pass