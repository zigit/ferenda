# -*- coding: utf-8 -*-
from __future__ import unicode_literals
# Intermediate base class containing some small functionality useful
# for handling data sources of swedish law.

from datetime import datetime, date
import re

from rdflib import URIRef, RDF, Namespace
from six import text_type as str
from layeredconfig import LayeredConfig

from ferenda import (DocumentRepository, DocumentStore, FSMParser,
                     CitationParser)
from ferenda import util
from ferenda.sources.legal.se.legalref import Link
from ferenda.elements.html import A, H1, H2, H3
from ferenda.elements import (Paragraph, Section, Body, CompoundElement,
                              SectionalElement)
from ferenda.pdfreader import Page

from . import RPUBL
# RPUBL = Namespace('http://rinfo.lagrummet.se/ns/2008/11/rinfo/publ#')
DCTERMS = Namespace(util.ns['dcterms'])
PROV = Namespace(util.ns['prov'])
FOAF = Namespace(util.ns['foaf'])


class Stycke(Paragraph):
    pass


class Sektion(Section):
    pass


class PreambleSection(CompoundElement):
    tagname = "div"
    classname = "preamblesection"
    counter = 0
    uri = None
    def as_xhtml(self, uri, parent_uri=None):
        if not self.uri:
            self.__class__.counter += 1
            self.uri = uri + "#PS%s" % self.__class__.counter
        element = super(PreambleSection, self).as_xhtml(uri, parent_uri)
        element.set('property', 'dcterms:title')
        element.set('content', self.title)
        element.set('typeof', 'bibo:DocumentPart')
        return element


class UnorderedSection(CompoundElement):
    tagname = "div"
    classname = "unorderedsection"
    counter = 0
    uri = None
    def as_xhtml(self, uri, parent_uri=None):
        if not self.uri:
            self.__class__.counter += 1
            # note that this becomes a document-global running counter
            self.uri = uri + "#US%s" % self.__class__.counter
        element = super(UnorderedSection, self).as_xhtml(uri, parent_uri)
        element.set('property', 'dcterms:title')
        element.set('content', self.title)
        element.set('typeof', 'bibo:DocumentPart')
        return element


class Appendix(SectionalElement): 
    tagname = "div"
    classname = "appendix"
    def as_xhtml(self, uri, parent_uri=None):
        if not self.uri:
            self.uri = uri + "#B%s" % self.ordinal

        return super(Appendix, self).as_xhtml(uri, parent_uri)


class Coverpage(CompoundElement):
    tagname = "div"
    classname = "coverpage"


class SwedishLegalStore(DocumentStore):

    """Customized DocumentStore."""

    def basefile_to_pathfrag(self, basefile):
        # "2012/13:152" => "2012-13/152"
        # "2012:152"    => "2012/152"
        return basefile.replace("/", "-").replace(":", "/")

    def pathfrag_to_basefile(self, pathfrag):
        # "2012-13/152" => "2012/13:152"
        # "2012/152"    => "2012:152"
        return pathfrag.replace("/", ":").replace("-", "/")

    def intermediate_path(self, basefile, attachment=None):
        return self.path(basefile, "intermediate", ".xml",
                         attachment=attachment)


class SwedishLegalSource(DocumentRepository):
    documentstore_class = SwedishLegalStore
    namespaces = ['rdf', 'rdfs', 'xsd', 'dcterms', 'skos', 'foaf',
                  'xhv', 'xsi', 'owl', 'prov', 'bibo',
                  ('rpubl', 'http://rinfo.lagrummet.se/ns/2008/11/rinfo/publ#'),
                  ('rinfoex', 'http://lagen.nu/terms#')]

    alias = "swedishlegalsource"

    lang = "sv"

    rdf_type = RPUBL.Rattsinformationsdokument  # subclasses override this

    # This is according to the RPUBL vocabulary: All
    # rpubl:Rattsinformationsdokument should have dcterms:title,
    # dcterms:issued (must be a xsd:date), dcterms:publisher and
    # dcterms:identifier
    required_predicates = [RDF.type, DCTERMS.title, DCTERMS.issued,
                           DCTERMS.identifier, PROV.wasGeneratedBy]

    swedish_ordinal_list = ('f\xf6rsta', 'andra', 'tredje', 'fj\xe4rde',
                            'femte', 'sj\xe4tte', 'sjunde', '\xe5ttonde',
                            'nionde', 'tionde', 'elfte', 'tolfte')

    swedish_ordinal_dict = dict(list(zip(
        swedish_ordinal_list, list(range(1, len(swedish_ordinal_list) + 1)))))

    swedish_months = {"januari": 1,
                      "jan": 1,
                      "februari": 2,
                      "feb": 2,
                      "febr": 2,
                      "mars": 3,
                      "mar": 3,
                      "april": 4,
                      "apr": 4,
                      "maj": 5,
                      "juni": 6,
                      "jun": 6,
                      "juli": 7,
                      "jul": 7,
                      "augusti": 8,
                      "aug": 8,
                      "september": 9,
                      "sep": 9,
                      "sept": 9,
                      "oktober": 10,
                      "okt": 10,
                      "november": 11,
                      "nov": 11,
                      "december": 12,
                      "dec": 12,
                      "\xe5r": 12}

    def __init__(self, config=None, **kwargs):
        super(SwedishLegalSource, self).__init__(config, **kwargs)
        if type(self) != SwedishLegalSource:
            assert self.alias != "swedishlegalsource", "Subclasses must override self.alias!"
        if not 'urlpath' in self.config:
            LayeredConfig.set(self.config, 'urlpath', "res/%s/" % self.alias)

    def get_default_options(self):
        opts = super(SwedishLegalSource, self).get_default_options()
        opts['pdfimages'] = False 
        return opts

    def _swedish_ordinal(self, s):
        sl = s.lower()
        if sl in self.swedish_ordinal_dict:
            return self.swedish_ordinal_dict[sl]
        return None

    def lookup_label(self, resource, predicate=FOAF.name):
        val = self.commondata.value(subject=URIRef(resource),
                                    predicate=predicate)
        if not val:
            raise KeyError(resource)
        else:
            return str(val)

    def sameas_uri(self, uri):
        # "http://localhost:8000/res/dir/2012:35" =>
        #     "http://rinfo.lagrummet.se/publ/dir/2012:35",
        # "http://localhost:8000/res/dv/hfd/2012:35" =>
        #     "http://rinfo.lagrummet.se/publ/rattsfall/hfd/2012:35"
        # 
        # but also:
        #
        # "https://lagen.nu/dom/hfd/2012:35" =>
        #     "http://rinfo.lagrummet.se/publ/rattsfall/hfd/2012:35"
        # "http://lagen.nu/1998:204" =>
        #     "http://rinfo.lagrummet.se/publ/sfs/1998:204"
        
        assert uri.startswith(self.config.url)
        
        # NOTE: This hardcodes what we can guess about other repos
        # and their .config.url + .config.urlpath
        maps = ((self.config.url+"res/dv/",
                 "http://rinfo.lagrummet.se/publ/rattsfall/"),
                (self.config.url+"res/",
                 "http://rinfo.lagrummet.se/publ/"),
                # Special hacky SFS handling (always starts digits 1 or 2)
                ("https://lagen.nu/1",
                 "http://rinfo.lagrummet.se/publ/sfs/1"),
                ("https://lagen.nu/2",
                 "http://rinfo.lagrummet.se/publ/sfs/2"),
                ("https://lagen.nu/dom",
                 "http://rinfo.lagrummet.se/publ/rattsfall"),
                ("https://lagen.nu/",
                 "http://rinfo.lagrummet.se/publ/"))
        for fr, to in maps:
            if uri.startswith(fr):
                return uri.replace(fr, to)

    def parse_iso_date(self, datestr):
        # only handles YYYY-MM-DD now. Look into dateutil or isodate
        # for more complete support of all ISO 8601 variants
        datestr = datestr.replace(" ","") # Data cleaning occasionally
                                          # needed. Maybe this isn't
                                          # the right place?
        return datetime.strptime(datestr, "%Y-%m-%d").date()

    def parse_swedish_date(self, datestr):
        """Parses a number of common forms of expressing swedish dates with
        varying precision.
        
        >>> parse_swedish_date("3 februari 2010")
        datetime.date(2010, 2, 3)
        >>> parse_swedish_date("vid utgången av december 1999")
        datetime.date(1999, 12, 31)
        >>> parse_swedish_date("november 1999")
        ferenda.util.gYearMonth(1999, 11)
        >>> parse_swedish_date("1998")
        ferenda.util.gYear(1999)

        """
        day = month = year = None
        # assume strings on the form "3 februari 2010"
        # strings on the form "vid utg\xe5ngen av december 1999"
        if datestr.startswith("vid utg\xe5ngen av"):
            import calendar
            (x, y, z, month, year) = datestr.split()
            month = self.swedish_months[month]
            year = int(year)
            day = calendar.monthrange(year, month)[1]
        else:
            # assume strings on the form "3 februari 2010", "8 dec. 1997"
            components =  datestr.split()
            year = int(components[-1])
            if len(components) >= 2:
                if components[-2].endswith("."):
                    components[-2] = components[-2][:-1]
                if components[-2] not in self.swedish_months:
                    raise ValueError(datestr)
                month = self.swedish_months[components[-2]]
            if len(components) >= 3:
                day = int(components[-3])

        # return the best we can
        if day:
            return date(year, month, day)
        if month:
            return util.gYearMonth(year, month)
        else:
            return util.gYear(year)

    def infer_triples(self, d, basefile):
        try:
            identifier = d.getvalue(self.ns['dcterms'].identifier)
            # if the identifier is incomplete, eg "2010/11:68" instead
            # of "Prop. 2010/11:68", the following triggers a
            # ValueError, which is handled the same as if no
            # identifier is available at all. Ideally,
            # sanitize_identifier should prevent all preventable
            # occurrences of this.
            (doctype, arsutgava, lopnummer) = re.split("[ :]", identifier)
        except (KeyError, ValueError):
            # Create one from basefile. First guess prefix
            if self.rdf_type == self.ns['rpubl'].Direktiv:
                prefix = "Dir. "
            elif self.rdf_type == self.ns['rpubl'].Utredningsbetankande:
                if d.getvalue(self.ns['rpubl'].utrSerie) == "http://rinfo.lagrummet.se/serie/utr/ds":
                    prefix = "Ds "
                else:
                    prefix = "SOU "
            elif self.rdf_type == self.ns['rpubl'].Proposition:
                prefix = "Prop. "
            elif self.rdf_type == self.ns['rpubl'].Forordningsmotiv:
                prefix = "Fm "
            else:
                raise ValueError("Cannot create dcterms:identifier for rdf_type %r" % self.rdf_type)
            identifier = "%s%s" % (prefix, basefile)
            
            self.log.warning(
                "%s: No dcterms:identifier, assuming %s" % (basefile, identifier))
            d.value(self.ns['dcterms'].identifier, identifier)

        # self.log.debug("Identifier %s" % identifier)
        (doctype, arsutgava, lopnummer) = re.split("[ :]", identifier)
        d.value(self.ns['rpubl'].arsutgava, arsutgava)
        d.value(self.ns['rpubl'].lopnummer, lopnummer)

# can't really have a toc_item thats general for all kinds of swedish legal documents?
# 
#    def toc_item(self, binding, row):
#        return {'uri': row['uri'],
#                'label': row['dcterms_identifier'] + ": " + row['dcterms_title']}


def offtryck_parser(basefile="0", preset="proposition", metrics={}):
    presets = {'default': {},
               'dir': {'footer': 920,
                       'header': 82,
                       'leftmargin': 105,
                       'rightmargin': 566,
                       'headingsize': 14,
                       'subheadingsize': 14,
                       'subheadingfamily': 'TimesNewRomanPS-ItalicMT',
                       'subsubheadingsize': None,
                       'textsize': 14},
               'proposition': {'footer': 920,
                               'header': 65, # make sure this is correct
                               'leftmargin': 160,
                               'rightmargin': 628,
                               'headingsize': 20,
                               'subheadingsize': 17,
                               'subheadingfamily': 'Times New Roman',
                               'subsubheadingsize': 15,
                               'textsize': 13},
               'sou': {'header': 49, # or rather 49 + 15
                       'header': 65, # make sure this is correct
                       'footer': 940,
                       'leftmargin': 84,
                       'rightmargin': 813,
                       'titlesize': 41,
                       'headingsize': 26,
                       'subheadingsize': 16,
                       'subheadingfamily': 'TradeGothic,Bold',
                       'subsubheadingsize': 14,
                       'textsize': 14
                   },
               'ds': {'header': 49, # or rather 49 + 15
                      'header': 65, # make sure this is correct
                      'footer': 940,
                      'leftmargin': 84,
                      'rightmargin': 813,
                      'titlesize': 41,
                      'headingsize': 26,
                      'subheadingsize': 16,
                      'subheadingfamily': 'TradeGothic,Bold',
                      'subsubheadingsize': 14,
                      'textsize': 14
                   }
               }
    if preset:
        metrics = presets[preset]

    # a mutable variable, which is accessible from the nested
    # functions
    state = {'pageno': 0,
             'appendixno': None,
             'preset': preset}

    def is_pagebreak(parser):
        return isinstance(parser.reader.peek(), Page)

    # page numbers, headings.
    def is_nonessential(parser):
        chunk = parser.reader.peek()
        if chunk.top > metrics['footer'] or chunk.bottom < metrics['header']:
            return True  # page numbers
        if (int(chunk.getfont()['size']) <= metrics['textsize'] and
                (chunk.left < metrics['leftmargin'] or
                 chunk.left > metrics['rightmargin']) and
            (15 <= len(str(chunk)) <= 29)): # matches both "Prop. 2013/14:1" and "Prop. 1999/2000:123 Bilaga 12"
            return True

    def is_coverpage(parser):
        # first 2 pages of a SOU are coverpages
        return isinstance(parser.reader.peek(), Page) and state['preset'] == "sou" and state['pageno'] < 2

            
    def is_preamblesection(parser):
        chunk = parser.reader.peek()
        if isinstance(chunk, Page):
            return False
        txt = str(chunk).strip()
        fontsize = int(chunk.getfont()['size'])
        if not metrics['subheadingsize'] <= fontsize <= metrics['headingsize']:
            return False

        for validheading in ('Propositionens huvudsakliga innehåll',
                             'Innehållsförteckning',
                             'Till statsrådet',
                             'Innehåll',
                             'Sammanfattning'):
            if txt.startswith(validheading):
                return True

    def is_section(parser):
        (ordinal, title) = analyze_sectionstart(parser)
        if ordinal:
            return ordinal.count(".") == 0

    def is_subsection(parser):
        (ordinal, title) = analyze_sectionstart(parser)
        if ordinal:
            return ordinal.count(".") == 1

    def is_unorderedsection(parser):
        # Subsections in "Författningskommentar" sections are
        # not always numbered. As a backup, check font size and family as well
        chunk = parser.reader.peek()
        return (int(chunk.getfont()['size']) == metrics['subheadingsize'] and
                chunk.getfont()['family'] == metrics['subheadingfamily'])

    def is_subsubsection(parser):
        (ordinal, title) = analyze_sectionstart(parser)
        if ordinal:
            return ordinal.count(".") == 2

    def is_appendix(parser):
        chunk = parser.reader.peek()
        txt = str(chunk).strip()
        if (chunk.getfont()['size'] == metrics['headingsize'] and txt.startswith("Bilaga ")):
            return True
        elif (int(chunk.getfont()['size']) == metrics['textsize'] and
              (chunk.left < metrics['leftmargin'] or
               chunk.left > metrics['rightmargin'])):
            m = re.search("Bilaga (\d)", str(chunk))
            if m:
                ordinal = int(m.group(1))
                if ordinal != state['appendixno']:
                    return True

    def is_paragraph(parser):
        return True

    def make_body(parser):
        return p.make_children(Body())
    setattr(make_body, 'newstate', 'body')

    def make_paragraph(parser):
        # if "Regeringen beslutade den 8 april 2010 att" in str(parser.reader.peek()):
        #     raise ValueError("OK DONE")
        return parser.reader.next()

    def make_coverpage(parser):
        state['pageno'] += 1
        parser.reader.next() # throwaway the Page object itself
        c = Coverpage()
        return parser.make_children(c)
    setattr(make_coverpage, 'newstate', 'coverpage')
        

    def make_preamblesection(parser):
        s = PreambleSection(title=str(parser.reader.next()).strip())
        if s.title == "Innehållsförteckning":
            parser.make_children(s) # throw away
            return None
        else:
            return parser.make_children(s)
    setattr(make_preamblesection, 'newstate', 'preamblesection')


    def make_unorderedsection(parser):
        s = UnorderedSection(title=str(parser.reader.next()).strip())
        return parser.make_children(s)
    setattr(make_unorderedsection, 'newstate', 'unorderedsection')

    def make_appendix(parser):
        # now, an appendix can begin with either the actual
        # headline-like title, or by the sidenote in the
        # margin. Find out which it is, and plan accordingly.
        done = False
        while not done:
            chunk = parser.reader.next()
            if isinstance(chunk, Page):
                continue
            m = re.search("Bilaga (\d)", str(chunk))
            if m:
                state['appendixno'] = int(m.group(1))
            if int(chunk.getfont()['size']) >= metrics['subheadingsize']:
                done = True
        s = Appendix(title=str(chunk).strip(),
                     ordinal=str(state['appendixno']),
                     uri=None)
        return parser.make_children(s)
    setattr(make_appendix, 'newstate', 'appendix')

    # this is used for subsections and subsubsections as well --
    # probably wont work due to the newstate property
    def make_section(parser):
        ordinal, title = analyze_sectionstart(parser, parser.reader.next())
        if ordinal:
            identifier = "Prop. %s, avsnitt %s" % (basefile, ordinal)
            s = Section(ordinal=ordinal, title=title)
        else:
            s = Section(title=str(title))
        return parser.make_children(s)
    setattr(make_section, 'newstate', 'section')

    def skip_nonessential(parser):
        parser.reader.next()
        return None

    def skip_pagebreak(parser):
        # increment pageno
        state['pageno'] += 1
        parser.reader.next()
        return None

    re_sectionstart = re.compile("^(\d[\.\d]*) +(.*[^\.])$").match
    def analyze_sectionstart(parser, textbox=None):
        if not textbox:
            textbox = parser.reader.peek()
        if not (metrics['headingsize'] >= int(textbox.getfont()['size']) >= metrics['subsubheadingsize']):
            return (None, textbox)
        txt = str(textbox)
        m = re_sectionstart(txt)
        if m:
            ordinal = m.group(1).rstrip(".")
            title = m.group(2)
            return (ordinal, title.strip())
        else:
            return (None, textbox)

    p = FSMParser()

    p.set_recognizers(is_coverpage,
                      is_pagebreak,
                      is_appendix,
                      is_nonessential,
                      is_section,
                      is_subsection,
                      is_subsubsection,
                      is_preamblesection,
                      is_unorderedsection,
                      is_paragraph)
    commonstates = ("body","preamblesection","section", "subsection", "unorderedsection", "subsubsection", "appendix")
    p.set_transitions({(commonstates, is_nonessential): (skip_nonessential, None),
                       (commonstates, is_pagebreak): (skip_pagebreak, None),
                       (commonstates, is_unorderedsection): (make_unorderedsection, "unorderedsection"),
                       (commonstates, is_paragraph): (make_paragraph, None),
                       ("body", is_coverpage): (make_coverpage, "coverpage"),
                       ("body", is_preamblesection): (make_preamblesection, "preamblesection"),
                       ("coverpage", is_coverpage): (False, None),
                       ("coverpage", is_preamblesection): (False, None),
                       ("coverpage", is_paragraph): (make_paragraph, None),
                       ("preamblesection", is_preamblesection): (False, None),
                       ("preamblesection", is_section): (False, None),
                       ("body", is_section): (make_section, "section"),
                       ("section", is_section): (False, None),
                       ("section", is_subsection): (make_section, "subsection"),
                       ("unorderedsection", is_preamblesection): (False, None),
                       ("unorderedsection", is_unorderedsection): (False, None),
                       ("unorderedsection", is_section): (False, None),
                       ("unorderedsection", is_appendix): (False, None),
                       ("subsection", is_subsection): (False, None),
                       ("subsection", is_section): (False, None),
                       ("subsection", is_subsubsection): (make_section, "subsubsection"),
                       ("subsubsection", is_subsubsection): (False, None),
                       ("subsubsection", is_subsection): (False, None),
                       ("subsubsection", is_section): (False, None),
                       ("body", is_appendix): (make_appendix, "appendix"),
                       (("appendix","subsubsection", "subsection", "section"), is_appendix):
                       (False, None)
                       })

    p.initial_state = "body"
    p.initial_constructor = make_body
    return p


def offtryck_gluefunc(textbox, nextbox, prevbox):
    linespacing = int(nextbox.getfont()['size']) / 2
    parindent = int(nextbox.getfont()['size'])
    if (textbox.getfont()['size'] == nextbox.getfont()['size'] and
        textbox.getfont()['family'] == nextbox.getfont()['family'] and
        textbox.top + textbox.height + linespacing > nextbox.top and
        ((prevbox.top + prevbox.height == nextbox.top + nextbox.height) or # compare baseline, not topline
         (prevbox.left == nextbox.left) or
         (parindent * 2 >= (prevbox.left - nextbox.left) >= parindent)
     )):
     return True
    
# (ab)use the CitationClass, with it's useful parse_recursive method,
# to use a legalref based parser instead of a set of pyparsing
# grammars.
class SwedishCitationParser(CitationParser):
    def __init__(self, legalrefparser, baseurl, allow_relative=False):
        self._legalrefparser = legalrefparser
        self._baseurl = baseurl
        self._currenturl = self._baseurl
        self._allow_relative = allow_relative
        if self._baseurl == "https://lagen.nu/":
            self._urlpath = ''
            self._dvpath = 'dom/'
            self._sfspath = ''
        else:
            self._urlpath = 'res/'
            self._dvpath = 'dv/'
            self._sfspath = 'sfs/'

    def parse_recursive(self, part, predicate="dcterms:references"):
        if hasattr(part, 'about'):
            self._currenturl = part.about
        elif hasattr(part, 'uri') and not isinstance(part, (Link, A)):
            self._currenturl = part.uri
        if isinstance(part, (Link, A, H1, H2, H3)):
            # don't process text that's already a link (or a heading)
            if isinstance(part, str): # caller expects a list
                return [part]
            else:
                return part
        else:
            return super(SwedishCitationParser, self).parse_recursive(part, predicate)
        
    def parse_string(self, string, predicate="dcterms:references"):
        try:
            from sfs import UpphavtKapitel, UpphavdParagraf
        except ImportError:
            from ferenda.sources.legal.se.sfs import UpphavtKapitel, UpphavdParagraf
        if isinstance(string, (UpphavtKapitel, UpphavdParagraf)):
            return [string]

        # basic normalization without stripping
        string = string.replace("\r\n", " ").replace("\n", " ")
        unfiltered = self._legalrefparser.parse(string,
                                                baseuri=self._currenturl,
                                                predicate=predicate,
                                                allow_relative=self._allow_relative)
        # remove those references that we cannot fully resolve (should
        # be an option in LegalRef, but...
        filtered = []
        for node in unfiltered:
            if isinstance(node, Link) and "sfs/9999:999" in node.uri:
                filtered.append(str(node))
            else:
                if isinstance(node, Link):
                    node.uri = self.localize_uri(node.uri)
                filtered.append(node)
        return filtered

    # a more complete version of DV.polish_metadata.localize_url
    # (which is used only on metadata fields, not body text)
    def localize_uri(self, uri):
        if "publ/rattsfall" in uri:
            return uri.replace("http://rinfo.lagrummet.se/publ/rattsfall/",
                               self._baseurl + self._urlpath + self._dvpath)
        elif "publ/sfs/" in uri:
            return uri.replace("http://rinfo.lagrummet.se/publ/sfs/",
                               self._baseurl + self._urlpath + self._sfspath)
        elif "publ/prop" in uri:
            return uri.replace("http://rinfo.lagrummet.se/publ/prop/",
                               self._baseurl + self._urlpath + "prop/")
        elif "publ/utr/sou" in uri:
            return uri.replace("http://rinfo.lagrummet.se/publ/utr/sou",
                               self._baseurl + self._urlpath + "sou/")
        elif "publ/utr/ds" in uri:
            return uri.replace("http://rinfo.lagrummet.se/publ/utr/ds",
                               self._baseurl + self._urlpath + "ds/")
        elif "publ/bet" in uri:
            return uri.replace("http://rinfo.lagrummet.se/publ/bet/",
                               self._baseurl + self._urlpath + "bet/")
        elif "publ/rskr" in uri:
            return uri.replace("http://rinfo.lagrummet.se/publ/rskr/",
                               self._baseurl + self._urlpath + "rskr/")
        else:
            return uri
