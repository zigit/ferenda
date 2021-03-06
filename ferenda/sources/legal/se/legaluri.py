# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *
"""This module constructs URIs for a document based on the properties
of that document. Alternatively, given a URI for a document, parse the
different properties for the document"""

# system libs
import re

# 3rdparty libs

from rdflib import Literal, Namespace, URIRef, Graph, BNode
from rdflib.term import Identifier
from rdflib import RDF
from rdflib.namespace import DCTERMS

# my own libraries
from ferenda.sources.legal.se.legalref import LegalRef
from ferenda import util
from ferenda.thirdparty.coin import URIMinter
from . import RPUBL, RINFOEX

# This dict maps keys used by the internal dictionaries that LegalRef
# constructs, which in turn are modelled after production rule names
# in the EBNF grammar.
predicate = {"type": RDF.type,
             "publikation": RPUBL.forfattningssamling,
             "arsutgava": RPUBL.arsutgava,
             "sidnummer": RPUBL.sidnummer,
             "lopnummer": RPUBL.lopnummer,
             "law": RPUBL.platsangivelse,  # FIXME: This pred is only proposed
             "chapter": RPUBL.kapitelnummer,
             "section": RPUBL.paragrafnummer,
             "piece": RINFOEX.styckenummer,
             "item": RINFOEX.punktnummer,
             "myndighet": DCTERMS.publisher,
             "domstol": DCTERMS.publisher,
             "rattsfallspublikation": RPUBL.rattsfallspublikation,  # probably?
             "dnr": RPUBL.diarienummer,
             "malnummer": RPUBL.malnummer,
             "avgorandedatum": RPUBL.avgorandedatum,
             "celex": RPUBL.genomforDirektiv}

dictkey = dict([[v, k] for k, v in list(predicate.items())])

types = {LegalRef.RATTSFALL: RPUBL.Rattsfallsreferat,
         LegalRef.LAGRUM: RPUBL.KonsolideradGrundforfattning,
         LegalRef.DOMSTOLSAVGORANDEN: RPUBL.VagledandeDomstolsavgorande,
         LegalRef.MYNDIGHETSBESLUT: RPUBL.VagledandeMyndighetsavgorande,
         LegalRef.FORESKRIFTER: RPUBL.Myndighetsforeskrift,
         LegalRef.EULAGSTIFTNING: RINFOEX.EUDirektiv}

dicttypes = dict([[v, k] for k, v in list(types.items())])

patterns = {LegalRef.RATTSFALL:
            re.compile(
                "http://rinfo.lagrummet.se/publ/rattsfall/(?P<publikation>\w+)/(?P<arsutgava>\d+)(s(?P<sidnummer>\d+)|((:| nr | ref )(?P<lopnummer>\d+)))").match,
            LegalRef.MYNDIGHETSBESLUT:
            re.compile(
                "http://rinfo.lagrummet.se/publ/beslut/(?P<myndighet>\w+)/(?P<dnr>.*)").match,
            LegalRef.LAGRUM:
            re.compile(
                "http://rinfo.lagrummet.se/publ/sfs/(?P<law>\d{4}:\w+)#?(K(?P<chapter>[0-9a-z]+))?(P(?P<section>[0-9a-z]+))?(S(?P<piece>[0-9a-z]+))?(N(?P<item>[0-9a-z]+))?").match
            }


# The dictionary should be a number of properties of the document we
# wish to construct the URI for, e.g:
# {"type": LegalRef.RATTSFALL,
#  "publikation": "nja",
#  "arsutgava": "2004"
#  "sidnr": "43"}
#
# The output is a URI string like 'http://rinfo.lagrummet.se/publ/rattsfall/nja/2004s43'
def construct(dictionary, minter=None):
    # Step 1: massage the data to a rdflib graph
    graph = Graph()
    bnode = BNode()
    for key in dictionary:
        if key == "law":
            # need to split any RPUBL.platsangivelse to
            # RPUBL.arsutgava + RPUBL.lopnummer since there is no uri
            # template for RPUBL.platsangivelse
            arsutgava, lopnummer = dictionary[key].split(":")
            graph.add((bnode, RPUBL.arsutgava, Literal(arsutgava)))
            graph.add((bnode, RPUBL.lopnummer, Literal(lopnummer)))
            # how to get the URI for eg SFS? It could be
            # <http://rinfo.lagrummet.se/serie/fs/sfs> or
            # <https://lagen.nu/dataset/sfs> (or really anything). The
            # truth is in slugs.n3 (which should be loaded in a
            # URIMinter object, but we don't have that). Let's
            # hardcode for now.
            graph.add((bnode, RPUBL.forfattningssamling,
                       URIRef("http://rinfo.lagrummet.se/serie/fs/sfs")))
        elif key in ("myndighet", "publikation", "rattsfallspublikation"):
            # need to lookup slugs eg "jk" to it's correct URI eg
            # <http://rinfo.lagrummet.se/org/justitiekanslern> (so
            # that we can turn it back to slugs again...
            g = Graph().parse("ferenda/sources/legal/se/res/uri/swedishlegalsource.slugs.ttl", format="turtle")
            SPACE = Namespace("http://rinfo.lagrummet.se/sys/uri/space#")
            uri = g.value(None, SPACE.abbrSlug, Literal(dictionary[key]))
            graph.add((bnode, predicate[key], uri))
        else:
            if isinstance(dictionary[key], Identifier):
                val = dictionary[key]
            elif key == "type":
                val = URIRef(types[dictionary[key]])
            else:
                val = Literal(dictionary[key])
            graph.add((bnode, predicate[key], val))
    return coinstruct_from_graph(graph, bnode, minter)


def _rpubl_uri_transform(s):
    # Inspired by
    # http://code.activestate.com/recipes/81330-single-pass-multiple-replace/
    table = {'å': 'aa',
             'ä': 'ae',
             'ö': 'oe'}
    r = re.compile("|".join(list(table.keys())))
    # return r.sub(lambda f: table[f.string[f.start():f.end()]], s.lower())
    return r.sub(lambda m: table[m.group(0)], s.lower())


def coinstruct_from_graph(graph, subject, minter=None):
    if not minter:
        configgraph = Graph()
        # FIXME: The configgraph should only be loaded once, but be
        # configurable ie load the correct COIN n3 config
        configgraph.parse("ferenda/sources/legal/se/res/uri/swedishlegalsource.space.ttl", format="turtle")
        configgraph.parse("ferenda/sources/legal/se/res/uri/swedishlegalsource.slugs.ttl", format="turtle")
        minter = URIMinter(configgraph,
                           URIRef("http://rinfo.lagrummet.se/sys/uri/space#"))
    result = minter.space.coin_uri(graph.resource(subject))
    return result   # only return the "best" ie most prioritized template

def construct_from_graph(graph):
    # assume every triple in the graph has the same bnode as subject
    bnode = list(graph)[0][0]
    assert(isinstance(bnode, BNode))

    # maybe we should just move the triples into a dict keyed on predicate?
    rdftype = graph.value(bnode, RDF.type, default=None, any=True)
    if rdftype == RPUBL.Rattsfallsreferat:
        publ = graph.value(bnode, RPUBL.rattsfallspublikation,
                           any=True)
        if str(publ) == "nja" and graph.value(bnode, RPUBL.sidnummer):
            # this creates URIs on the form
            # http://rinfo.lagrummet.se/publ/rf/nja/2005/s_523
            uripart = "%s/%ss%s" % (publ,
                                    graph.value(bnode, RPUBL.arsutgava),
                                    graph.value(bnode, RPUBL.sidnummer))
        else:
            uripart = "%s/%s:%s" % (publ,
                                    graph.value(bnode, RPUBL.arsutgava),
                                    graph.value(bnode, RPUBL.lopnummer))

        return "http://rinfo.lagrummet.se/publ/rattsfall/%s" % uripart
    elif rdftype == RPUBL.KonsolideradGrundforfattning:
        # print graph.serialize(format="n3")
        attributeorder = [RINFOEX.kapitelnummer,
                          RINFOEX.paragrafnummer,
                          RINFOEX.styckenummer,
                          RINFOEX.punktnummer]
        signs = {RINFOEX.kapitelnummer: 'K',
                 RINFOEX.paragrafnummer: 'P',
                 RINFOEX.styckenummer: 'S',
                 RINFOEX.punktnummer: 'N'}
        urifragment = graph.value(bnode, RPUBL.lopnummer)
        for key in attributeorder:
            if graph.value(bnode, key):
                if "#" not in urifragment:
                    urifragment += "#"
                urifragment += signs[key] + graph.value(bnode, key)
        return "http://rinfo.lagrummet.se/publ/sfs/%s" % urifragment

    elif rdftype == RPUBL.VagledandeMyndighetsavgorande:
        return "http://rinfo.lagrummet.se/publ/avg/%s/%s" % \
               (graph.value(bnode, DCTERMS.creator),
                graph.value(bnode, RPUBL.diarienummer))

    elif rdftype == RPUBL.VagledandeDomstolsavgorande:
        return "http://rinfo.lagrummet.se/publ/dom/%s/%s/%s" % \
               (graph.value(bnode, DCTERMS.creator),
                graph.value(bnode, RPUBL.malnummer),
                graph.value(bnode, RPUBL.avgorandedatum))

    elif rdftype == RPUBL.Myndighetsforeskrift:
        return "http://rinfo.lagrummet.se/publ/%s/%s:%s" % \
               (_rpubl_uri_transform(graph.value(bnode, RPUBL.forfattningssamling)),
                graph.value(bnode, RPUBL.arsutgava),
                graph.value(bnode, RPUBL.lopnummer))
    elif rdftype == RINFOEX.EUDirektiv:
        return ("http://rinfo.lagrummet.se/ext/eur-lex/%s" %
                graph.value(bnode, RPUBL.genomforDirektiv))
    else:
        raise ValueError("Don't know how to construct a uri for %s" % rdftype)


def parse(uri):
    graph = parse_to_graph(uri)
    dictionary = {}
    for (subj, pred, obj) in graph:
        if pred == RDF.type:
            dictionary["type"] = dicttypes[obj]
        else:
            dictionary[dictkey[pred]] = str(obj)
    return dictionary

def parse_to_graph(uri):
    dictionary = None
    for (pid, pattern) in list(patterns.items()):
        m = pattern(uri)
        if m:
            dictionary = m.groupdict()
            dictionary["type"] = pid
            break

    if not dictionary:
        raise ValueError("Can't parse URI %s" % uri)

    graph = Graph()
    for key, value in list(util.ns.items()):
        graph.bind(key, Namespace(value))
    bnode = BNode()
    for key in dictionary:
        if dictionary[key] is None:
            continue
        if key.startswith("_"):
            continue
        if key == "type":
            graph.add((bnode, RDF.type, URIRef(types[dictionary[key]])))
        else:
            graph.add((bnode, predicate[key], Literal(dictionary[key])))

    return graph
