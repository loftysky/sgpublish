import os

from sgpublish.publisher import Publisher


class Exporter(object):
    
    def __init__(self, workspace=None, filename_hint=None, publish_type=None):
        self._workspace = workspace
        self._filename_hint = filename_hint
        self._publish_type = publish_type

    @property
    def publish_type(self):
        """The type of publish to create for this exporter."""
        return self._publish_type
    
    @property
    def filename_hint(self):
        """A filename for extracting info from, or using as a base to construct
        the final path if not supplied."""
        return self._filename_hint
    
    @property
    def workspace(self):
        """The working directory, usually corresponds to an SGFS tag."""
        return self._workspace or os.getcwd()
    
    def get_previous_publish_ids(self):
        """A set of previous publish IDs that current context was involved in.
        
        These publishes are used by the GUI to determine which publish stream
        to automatically select.
        
        Currently only supported in the Maya classes; please extend for your
        applications.
        
        """
        return set()
    
    def record_publish_id(self, id_):
        """Save the new publish ID in the current scene/script/context.
        
        These publishes will later be returned by :meth:`get_previous_publish_ids`.
        
        Currently only supported in the Maya classes; please extend for your
        applications.
        
        """
        pass
    
    def publish(self, link=None, name=None, export_kwargs=None, **publisher_kwargs):
        """Trigger a publish.
        
        This method only deals with setting up the publisher, and uses
        :meth:`export_publish` to do the work.
        
        :param export_kwargs: Passed to :meth:`export_publish`.
        :returns: The publisher used.
        
        """

        type_ = self.publish_type
        if not type_:
            raise ValueError('cannot publish without type')

        publisher_kwargs.pop('type', None)
        with Publisher(link=link, type=type_, name=name, **publisher_kwargs) as publisher:
            
            # Record the ID before the export so that it is included.
            self.record_publish_id(publisher.id)
            
            # This is a hook that everyone should allow to go up the full chain.
            self.before_export_publish(publisher, **export_kwargs)
            
            # Completely overridable by children (without calling super).
            self.export_publish(publisher, **export_kwargs)
            
            return publisher
    
    def before_export_publish(self, publisher, **kwargs):
        pass
    
    def fields_for_review_version(self, **kwargs):
        return {}
    
    def export_publish(self, publisher, **kwargs):
        """Perform an export within the context of a publish.
        
        By default this simply calls :meth:`export` with the publish directory
        and no path.
        
        :param kwargs: Passed to :meth:`export_publish`.
        
        """
        return self.export(publisher.directory, None, **kwargs)
    
    def export(self, directory, path, **kwargs):
        """Do the work of exporting. Must be implemented in subclasses.
        
        :param str directory: The directory to publish in. If ``path`` is present
            then this may be assumed equal to ``os.path.dirname(path)``.
        :param path: The path to export to. Will always be ``None`` when
            publishing, and future use of ``None`` is reserved for complex
            exports, such as geocaches.
        :type path: str or None
        :param kwargs: Extra keyword arguments passed from the exporting widgets.
        
        """
        raise NotImplementedError()



