# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *


class TocPageset(object):

    """Represents a particular set of TOC pages, structured around some
    particular attribute(s) of documents, like title or publication
    date. :py:meth:`~ferenda.DocumentRepository.toc_pagesets` returns
    a list of these objects, override that method to provide custom
    TocPageset objects.

    :param label: A description of this set of TOC pages, like
                  "By publication year"
    :type  label: str
    :param pages: The set of :py:class:`~ferenda.TocPage` objects that makes
                  up this page set.
    :type  pages: list
    :param predicate: The RDFLib predicate (if any) that this pageset is
                      keyed on.
    :type  predicate: rdflib.term.URIRef
    """

    def __init__(self, label, pages, predicate=None):
        self.label = label
        self.pages = pages
        self.predicate = predicate

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __lt__(self, other):
        # the default sort order when sorting a list of pagesets is by
        # the associated RDF predicate.
        return self.predicate < other.predicate
        
    def __repr__(self):
        dictrepr = "".join(
            (" %s=%s" %
             (k, v) for k, v in sorted(
                 self.__dict__.items()) if not callable(v)))
        return ("<%s%s>" % (self.__class__.__name__, dictrepr))
