import inspect
import os
import logging
import pkg_resources
import shutil
from contextlib import contextmanager

from ferenda import util
from ferenda.errors import ResourceNotFound


class ResourceLoader(object):

    # should perhaps have a corresponding make_modulepath for use with
    # pkg_resources.resource_stream et al
    @staticmethod
    def make_loadpath(instance, suffix="res"):
        """Given an object instance, returns a list of path locations
        corresponding to the physical location of the implementation
        of that instance, with a specified suffix.

        ie. if provided an ``Foo`` instance, whose class is defined in
        project/subclass/foo.py, and ``Foo`` derives from ``Bar``,
        whose class is defined in project/bar.py, the returned
        make_loadpath will return ``['project/subclass/res',
        'project/res']``

        """
        res = []
        for cls in inspect.getmro(instance.__class__):
            if cls == object:
                continue
            path = os.path.relpath(inspect.getfile(cls))
            candidate = os.path.dirname(path) + os.sep + suffix
            # uniquify loadpath
            if candidate not in res and os.path.exists(candidate):
               res.append(candidate)
        return res

    def __init__(self, *loadpath, **kwargs):
        """
        Encapsulates resource access through a flexible load-path system.

        :param loadpath: A list of directories to search for by the
                         instance methods (in priority order) .
        :param kwargs: Any other named parameters to initialize the
                       object with. The only named parameter defined
                       is ``use_pkg_resources`` (default: True) for
                       specifying whether to use the
                       `<https://pythonhosted.org/setuptools/pkg_resources.html#resourcemanager-api>
                       ResourceManager API`_ in addition to regular
                       file operations. If set, the ResourceManager
                       API is queried only after all directories in
                       loadpath are searched.

        """
        self.loadpath = loadpath
        self.use_pkg_resources = kwargs.get("use_pkg_resources", True)
        self.modulename = "ferenda"
        self.resourceprefix = "res"
        self.log = logging.getLogger(__name__)

    def exists(self, resourcename):
        """Returns True iff the named resource can be found anywhere in any
        place where this loader searches, False otherwise"""
        try:
            self.filename(resourcename)
            return True
        except ResourceNotFound:
            return False

    def load(self, resourcename, binary=False):
        """Returns the contents of the resource, either as a string or a bytes
        object, depending on whether ``binary`` is False or True.
        
        Might raise :py:exc:`~ferenda.errors.ResourceNotFound`.
        """
        mode = "rb" if binary else "r"
        filename = self.filename(resourcename)
        self.log.debug("Loading %s" % filename)
        with open(filename, mode=mode) as fp:
            return fp.read()

    # this works like old-style open, eg.
    # fp = loader.open(...)
    # fp.read()
    # fp.close()
    def openfp(self, resourcename, binary=False):
        """Opens the specified resource and returns a open file object. 
        Caller must call .close() on this object when done.

        Might raise :py:exc:`~ferenda.errors.ResourceNotFound`.
        """
        mode = "rb" if binary else "r"
        filename = self.filename(resourcename)
        self.log.debug("Opening fp %s" % filename)
        return open(filename, mode=mode)

    # this is used with 'with', eg.
    # with loader.open(...) as fp:
    #     fp.read()
    @contextmanager
    def open(self, resourcename, binary=False):
        """Opens the specified resource as a context manager, ie call with
        ``with``:

            >>> loader = ResourceLoader()
            >>> with resource.open("robots.txt") as fp:
            ...     fp.read()

        Might raise :py:exc:`~ferenda.errors.ResourceNotFound`.

        """
        mode = "rb" if binary else "r"
        fp = None
        try:
            filename = self.filename(resourcename)
            self.log.debug("Opening %s" % filename)
            fp = open(filename, mode=mode)
            yield fp
        except ResourceNotFound:
            raise
        finally:
            if fp:
                fp.close()

    def filename(self, resourcename):
        """Return a filename pointing to the physical location of the resource.
        If the resource is only found using the ResourceManager API, extract '
        the resource to a temporary file and return its path.
        
        Might raise :py:exc:`~ferenda.errors.ResourceNotFound`.
        """
        if os.path.isabs(resourcename):  # don't examine the loadpath
            if os.path.exists(resourcename):
                return resourcename
            else:
                raise ResourceNotFound(resourcename)
        for path in self.loadpath:
            candidate = path + os.sep + resourcename
            if os.path.exists(candidate):
                return candidate
        if (self.use_pkg_resources and
            pkg_resources.resource_exists(self.modulename,
                                          self.resourceprefix + os.sep + resourcename)):
            abspath = pkg_resources.resource_filename(self.modulename, self.resourceprefix + os.sep + resourcename)
            return os.path.relpath(abspath)
        raise ResourceNotFound(resourcename) # should contain a list of places we searched?
                
    def extractdir(self, resourcedir, target):
        """Extract all file resources directly contained in the specified
        resource directory.
        
        Searches all loadpaths and optionally the Resources API for
        any file contained within. This means the target dir may end
        up with eg. one file from a high-priority path and other files
        from the system dirs/resources. This in turns makes it easy to
        just override a single file in a larger set of resource files.

        """
        extracted = set()
        for path in self.loadpath:
            if resourcedir:
                path = path+os.sep+resourcedir
            if not os.path.exists(path):
                continue
            for f in os.listdir(path):
                src = os.sep.join([path, f])
                dest = os.sep.join([target, f])
                if dest not in extracted and os.path.isfile(src):
                    util.ensure_dir(dest)
                    shutil.copy2(src, dest)
                    extracted.add(dest)
        if self.use_pkg_resources:
            path = self.resourceprefix
            if resourcedir:
                path = path + os.sep + resourcedir
            for f in pkg_resources.resource_listdir(self.modulename, path):
                src = path + os.sep + f
                dest = target
                if resourcedir:
                    dest = target + os.sep + resourcedir
                dest += os.sep + f
                if (dest not in extracted and not
                    pkg_resources.resource_isdir(self.modulename,
                                                 self.resourceprefix + os.sep + f)):
                    util.ensure_dir(dest)
                    with open(dest, "wb") as fp:
                        readfp = pkg_resources.resource_stream(self.modulename,
                                                               src)
                        fp.write(readfp.read())
                    extracted.add(dest)
