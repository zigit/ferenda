# base class that abstracts acess to the EUR-Lex web services and the
# Cellar repository. Uses CELEX ids for basefiles, but stores them
# sharded per year
from lxml import etree
from io import BytesIO
import requests
import os
import re
from math import ceil
from html import escape
import email
import tempfile

import requests
from bs4 import BeautifulSoup
from rdflib import Graph, Namespace, URIRef
from rdflib.resource import Resource
from rdflib.namespace import OWL

from ferenda import util, decorators, errors
from ferenda import DocumentRepository, DocumentStore

class EURLexStore(DocumentStore):
    downloaded_suffixes = [".fmx4", ".xhtml", ".html", ".pdf"]
    def basefile_to_pathfrag(self, basefile):
        if basefile.startswith("."):
            return basefile
        # Shard all files under year, eg "32017R0642" => "2017/32017R0642"
        year = basefile[1:5]
        assert year.isdigit(), "%s doesn't look like a legit CELEX" % basefile
        return "%s/%s" % (year, basefile)

    def pathfrag_to_basefile(self, pathfrag):
        if pathfrag.startswith("."):
            return pathfrag
        year, basefile = pathfrag.split("/", 1)
        return basefile
    

# this implements some common request.Response properties/methods so
# that it can be used in plpace of a real request.Response object
class FakeResponse(object):

    def __init__(self, status_code, text, headers):
        self.status_code = status_code
        self.text = text
        self.headers = headers

    @property
    def content(self):
        default = "text/html; encoding=utf-8"
        encoding = self.headers.get("Content-type", default).split("encoding=")[1]
        return self.text.encode(encoding)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ValueError(self.status_code)
        
        
    
class EURLex(DocumentRepository):
    alias = "eurlex"
    start_url = "http://eur-lex.europa.eu/eurlex-ws?wsdl"
    pagesize = 100 # 100 max allowed by the web service
    expertquery_template = "" # sub classes adjust this
    download_iterlinks = False
    lang = "sv"
    languages = ["swe", "eng"]
    documentstore_class = EURLexStore
    downloaded_suffix = ".xhtml"
    download_accept_406 = True
    contenttype = "application/xhtml+xml" 
    namespace = "{http://eur-lex.europa.eu/search}"
    download_archive = False
    
    @classmethod
    def get_default_options(cls):
        opts = super(EURLex, cls).get_default_options()
        opts['languages'] = ['eng']
        opts['curl'] = True  # if True, the web service is called
                              # with command-line curl, not the
                              # requests module (avoids timeouts)
        return opts

    def dump_graph(self, celexid, graph):
        with self.store.open_intermediate(celexid, "wb", suffix=".ttl") as fp:
            fp.write(graph.serialize(format="ttl"))

    def query_webservice(self, query, page):
        # this is the only soap template we'll need, so we include it
        # verbatim to avoid having a dependency on a soap module like
        # zeep.
        endpoint = 'http://eur-lex.europa.eu/EURLexWebService'
        envelope = """<soap-env:Envelope xmlns:soap-env="http://www.w3.org/2003/05/soap-envelope">
  <soap-env:Header>
    <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <wsse:UsernameToken>
        <wsse:Username>%s</wsse:Username>
        <wsse:Password Type="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText">%s</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soap-env:Header>
  <soap-env:Body>
    <sear:searchRequest xmlns:sear="http://eur-lex.europa.eu/search">
      <sear:expertQuery>%s</sear:expertQuery>
      <sear:page>%s</sear:page>
      <sear:pageSize>%s</sear:pageSize>
      <sear:searchLanguage>%s</sear:searchLanguage>
    </sear:searchRequest>
  </soap-env:Body>
</soap-env:Envelope>
""" % (self.config.username, self.config.password, escape(query, quote=False), page, self.pagesize, self.lang)
        headers = {'Content-Type': 'application/soap+xml; charset=utf-8; action="http://eur-lex.europa.eu/EURLexWebService/doQuery"',
                   'SOAPAction': 'http://eur-lex.europa.eu/EURLexWebService/doQuery'}
        if self.config.curl:
            # dump the envelope to a tempfile
            headerstr = ""
            for k, v in headers.items():
                assert "'" not in v  # if it is, we need to work on escaping it
                headerstr += " --header '%s: %s'" % (k, v)
            with tempfile.NamedTemporaryFile() as fp:
                fp.write(envelope.encode("utf-8"))
                fp.flush()
                envelopename = fp.name
                headerfiledesc, headerfilename = tempfile.mkstemp()
                cmd = 'curl -X POST -D %(headerfilename)s --data-binary "@%(envelopename)s" %(headerstr)s %(endpoint)s' % locals()
                (ret, stdout, stderr) = util.runcmd(cmd)
            headerfp = os.fdopen(headerfiledesc)
            header = headerfp.read()
            headerfp.close()
            util.robust_remove(headerfilename)
            status, headers = header.split('\n', 1)
            prot, code, msg = status.split(" ", 2)
            headers = dict(email.message_from_string(headers).items())
            res = FakeResponse(int(code), stdout, headers)
        else:
            res = util.robust_fetch(self.session.post, url
                                    , self.log,
                                    raise_for_status=False,
                                    data=envelope,
                                    headers=headers,
                                    timeout=10)
            
        if res.status_code == 500:
            tree = etree.parse(BytesIO(res.content))
            statuscode = tree.find(".//{http://www.w3.org/2003/05/soap-envelope}Subcode")[0].text
            statusmsg = tree.find(".//{http://www.w3.org/2003/05/soap-envelope}Text").text
            raise errors.DownloadError("%s: %s" % (statuscode, statusmsg))
        return res
        
    def construct_expertquery(self, query_template):
        if 'lastdownload' in self.config and not self.config.refresh:
            query_template += self.config.lastdownload.strftime(" AND DD >= %d/%m/%Y")
        query_template += " ORDER BY DD ASC"
        self.log.info("Query: %s" % query_template)
        return query_template
    
    def download_get_first_page(self):
        return self.query_webservice(self.construct_expertquery(self.expertquery_template), 1)

    def get_treenotice_graph(self, cellarurl, celexid):
        # avoid HTTP call if we already have the data
        if os.path.exists(self.store.intermediate_path(celexid, suffix=".ttl")):
            self.log.info("%s: Opening existing TTL file" % celexid)
            with self.store.open_intermediate(celexid, suffix=".ttl") as fp:
                return Graph().parse(data=fp.read(), format="ttl")
        # FIXME: read the rdf-xml data line by line and construct a
        # graph by regex-parsing interesting lines with a very simple
        # state machine, rather than doing a full parse, to speed
        # things up
        resp = util.robust_fetch(self.session.get, cellarurl, self.log, headers={"Accept": "application/rdf+xml;notice=tree"}, timeout=10)
        if not resp:
            return None
        with util.logtime(self.log.info,
                          "%(basefile)s: parsing the tree notice took %(elapsed).3f s",
                          {'basefile': celexid}):
            graph = Graph().parse(data=resp.content)
        return graph
    
    def find_manifestation(self, cellarid, celexid):
        cellarurl = "http://publications.europa.eu/resource/cellar/%s?language=%s" % (cellarid, self.languages[0])
        graph = self.get_treenotice_graph(cellarurl, celexid)
        if graph is None:
            return None, None, None, None
        
        # find the root URI -- it might be on the form
        # "http://publications.europa.eu/resource/celex/%s", but can
        # also take other forms (at least for legislation)
        # At the same time, find all expressions of this work (ie language versions).
        CDM = Namespace("http://publications.europa.eu/ontology/cdm#")
        CMR = Namespace("http://publications.europa.eu/ontology/cdm/cmr#")
        root = None
        candidateexpressions = {}
        for expression, work in graph.subject_objects(CDM.expression_belongs_to_work):
            assert root is None or work == root
            root = work
            expression = Resource(graph, expression)
            lang = expression.value(CDM.expression_uses_language)
            lang = str(lang.identifier).rsplit("/", 1)[1].lower()
            if lang in self.config.languages:
                candidateexpressions[lang] = expression

        if not candidateexpressions:
            self.log.warning("%s: Found no suitable languages" % celexid)
            self.dump_graph(celexid, graph)
            return None, None, None, None

        for lang in self.config.languages:
            if lang in candidateexpressions:
                expression = candidateexpressions[lang]
                candidateitem = {}
                # we'd like to order the manifestations in some preference order -- xhtml > html > pdf
                for manifestation in expression.objects(CDM.expression_manifested_by_manifestation):
                    manifestationtype = str(manifestation.value(CDM.type))
                    # there might be multiple equivalent
                    # manifestations, eg
                    # ...celex/62001CJ0101.SWE.fmx4,
                    # ...ecli/ECLI%3AEU%3AC%3A2003%3A596.SWE.fmx4 and
                    # ...cellar/bcc476ae-43f8-4668-8404-09fad89c202a.0011.01. Try
                    # to find out if that is the case, and get the "root" manifestation
                    rootmanifestations = list(manifestation.subjects(OWL.sameAs))
                    if rootmanifestations:
                        manifestation = rootmanifestations[0]
                    items = list(manifestation.subjects(CDM.item_belongs_to_manifestation))
                    if len(items) == 1:
                        candidateitem[manifestationtype] = items[0]
                if candidateitem:
                    for t in ("fmx4", "xhtml", "html", "pdf", "pdfa1a"):
                        if t in candidateitem:
                            item = candidateitem[t]
                            mimetype = str(item.value(CMR.manifestationMimeType))
                            self.log.info("%s: Has manifestation %s (%s) in language %s" % (celexid, t,mimetype, lang))
                            # we might need this even outside of
                            # debugging (eg when downloading
                            # eurlexcaselaw, the main document lacks
                            # keywords, classifications, instruments
                            # cited etc.
                            self.dump_graph(celexid, graph) 
                            return lang, t, mimetype, str(item.identifier)
                else:
                    if candidateitem:
                        self.log.warning("%s: Language %s had no suitable manifestations" %
                                         (celexid, lang))
        self.log.warning("%s: No language (tried %s) had any suitable manifestations" % (celexid, ", ".join(candidateexpressions.keys())))
        self.dump_graph(celexid, graph)
        return None, None, None, None

    
    def download_single(self, basefile, url=None):
        if url is None:
            result = self.query_webservice("DN = %s" % basefile, page=1)
            result.raise_for_status()
            tree = etree.parse(BytesIO(result.content))
            results = tree.findall(".//{http://eur-lex.europa.eu/search}result")
            assert len(results) == 1
            result = results[0]
            cellarid = result.find(".//{http://eur-lex.europa.eu/search}reference").text
            cellarid = re.split("[:_]", cellarid)[2]

            celex = result.find(".//{http://eur-lex.europa.eu/search}ID_CELEX")[0].text
            match = self.celexfilter(celex)
            assert match
            celex = match.group(1)
            assert celex == basefile
            lang, filetype, mimetype, url = self.find_manifestation(cellarid, celex)
            # FIXME: This is an ugly way of making sure the downloaded
            # file gets the right suffix (due to
            # DocumentStore.downloaded_path choosing a filename from among
            # several possible suffixes based on what file already exists
            downloaded_path = self.store.path(basefile, 'downloaded', '.'+filetype)
            if not os.path.exists(downloaded_path):
                util.writefile(downloaded_path, "")
        return super(EURLex, self).download_single(basefile, url)

    @decorators.downloadmax
    def download_get_basefiles(self, source):
        totalhits = None
        done = False
        page = 1
        processedhits = 0
        while not done:
            tree = etree.parse(BytesIO(source.encode("utf-8")))
            if totalhits is None:
                totalhits = int(tree.find(".//{http://eur-lex.europa.eu/search}totalhits").text)
                self.log.info("Total hits: %s" % totalhits)
            results = tree.findall(".//{http://eur-lex.europa.eu/search}result")
            self.log.info("Page %s: %s results" % (page, len(results)))
            for idx, result in enumerate(results):
                processedhits += 1
                cellarid = result.find(".//{http://eur-lex.europa.eu/search}reference").text
                cellarid = re.split("[:_]", cellarid)[2]
                celex = result.find(".//{http://eur-lex.europa.eu/search}ID_CELEX")[0].text
                try:
                    title = result.find(".//{http://eur-lex.europa.eu/search}EXPRESSION_TITLE")[0].text
                except TypeError:
                    self.log.info("%s: Lacks title, the resource might not be available in %s" % (celex, self.lang))
                match = self.celexfilter(celex)
                if not match:
                    self.log.info("%s: Not matching current filter, skipping" % celex)
                    continue
                celex = match.group(1)
                self.log.debug("%3s: %s %.55s %s" % (idx + 1, celex, title, cellarid))
                lang, filetype, mimetype, url = self.find_manifestation(cellarid, celex)
                if filetype:
                    # FIXME: This is an ugly way of making sure the downloaded
                    # file gets the right suffix (due to
                    # DocumentStore.downloaded_path choosing a filename from among
                    # several possible suffixes based on what file already exists
                    downloaded_path = self.store.path(celex, 'downloaded', '.'+filetype)
                    if not os.path.exists(downloaded_path):
                        util.writefile(downloaded_path, "")
                    yield celex, url
            page += 1
            done = processedhits >= totalhits
            if not done:
                self.log.info("Getting page %s (out of %s)" % (page, ceil(totalhits/self.pagesize)))
                result = self.query_webservice(self.construct_expertquery(self.expertquery_template), page)
                result.raise_for_status()
                source = result.text

#    def _addheaders(self, url, filename=None):
#        headers = super(EURLex, self)._addheaders(filename)
#        headers["Accept"] = self.contenttype
#        key, lang = url.split("?")[1].split("=")
#        assert key == "language"
#        headers["Accept-Language"] = lang
#        return headers

