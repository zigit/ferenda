# -*- coding: utf-8 -*-

# This fixture does a bunch of real HTTP request against a selected
# server (determined by the environment variable FERENDA_TESTURL,
# which is http://localhost:8080/
#
# When running against a local instance, it's important that this has
# been initialized with the documents in lagen/nux

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *

# sys
import os
import unittest
import codecs
import re


# 3rdparty
import requests
from bs4 import BeautifulSoup
from rdflib import Graph, URIRef
from rdflib.namespace import DCTERMS

# own
from ferenda.elements import Link, serialize
from ferenda.testutil import FerendaTestCase
from lagen.nu import SFS, LNKeyword
from lagen.nu.wsgiapp import WSGIApp

class TestLagen(unittest.TestCase, FerendaTestCase):

    baseurl = os.environ.get("FERENDA_TESTURL", "http://localhost:8080/")

    def assert_status(self, url, code):
        res = requests.get(url, headers={'Accept': 'text/html'})
        self.assertEqual(res.status_code, code)
        return res
    
    def assert200(self, url):
        return self.assert_status(url, 200)

    def assert404(self, url):
        return self.assert_status(url, 404)

    def get(self, url, **kwargs):
        if 'headers' not in kwargs:
            kwargs['headers']={'Accept': 'text/html'}
        return requests.get(url, **kwargs)
    

class TestPaths(TestLagen):

    def test_frontpage(self):
        self.assert200(self.baseurl)

    def test_nonexist(self):
        self.assert404(self.baseurl + "this-resource-does-not-exist")

    def test_specific_sfs(self):
        self.assert200(self.baseurl + "1998:204")

    def test_specific_dv(self):
        self.assert200(self.baseurl + "dom/nja/2015s180") # basefile HDO/Ö6229-14

    def test_specific_keyword(self):
        self.assert200(self.baseurl + "begrepp/Personuppgift")
        
    def test_specific_keyword_tricky(self):
        self.assert200(self.baseurl + "begrepp/Sekundär_sekretessbestämmelse")


class TestPages(TestLagen):
    def test_frontpage_links(self):
        # <a> elements should have a href attribute (you'd think that
        # was obvious, but it's not)
        res = self.get(self.baseurl)
        soup = BeautifulSoup(res.text, "lxml")
        firstlink = soup.article.a
        self.assertTrue(firstlink.get("href"))

class TestPatching(TestLagen):

    def test_file_has_been_patched(self):
        needle = codecs.encode("Fjrebgrp", encoding="rot13")# rot13 of a sensitive name
        res = self.get(self.baseurl + "dom/nja/2002s35")    # case containing sensitive info
        res.raise_for_status()                              # req succeded
        self.assertEqual(-1, res.text.find(needle))         # sensitive name is removed
        self.assertTrue(res.text.index("alert alert-warning patchdescription")) # patching is advertised

class TestConNeg(TestLagen):
    # this basically mirrors testWSGI.ConNeg
    def test_basic(self):
        res = self.get(self.baseurl + "1991:1469")
        self.assertEqual(200, res.status_code)
        self.assertEqual("text/html; charset=utf-8", res.headers['Content-Type'])

    def test_xhtml(self):
        res = self.get(self.baseurl + "1991:1469",
                       headers={'Accept': 'application/xhtml+xml'})
        self.assertEqual(200, res.status_code)
        self.assertEqual("application/xhtml+xml", res.headers['Content-Type'])
        # variation: use file extension
        res = self.get(self.baseurl + "1991:1469.xhtml")
        self.assertEqual(200, res.status_code)
        self.assertEqual("application/xhtml+xml", res.headers['Content-Type'])

    def test_rdf(self):
        # basic test 3: accept: application/rdf+xml -> RDF statements (in XML)
        res = self.get(self.baseurl + "1991:1469",
                       headers={'Accept': 'application/rdf+xml'})
        self.assertEqual(200, res.status_code)
        self.assertEqual("application/rdf+xml", res.headers['Content-Type'])
        # variation: use file extension
        res = self.get(self.baseurl + "1991:1469.rdf")
        self.assertEqual(200, res.status_code)
        self.assertEqual("application/rdf+xml", res.headers['Content-Type'])

    def test_ntriples(self):
        # transform test 4: accept: text/plain -> RDF statements (in NTriples)

        # get the untransformed data to compare with
        g = Graph().parse(data=self.get(self.baseurl + "1991:1469.rdf").text)
        res = self.get(self.baseurl + "1991:1469",
                       headers={'Accept': 'text/plain'})
        self.assertEqual(200, res.status_code)
        self.assertEqual("text/plain", res.headers['Content-Type'])
        got = Graph().parse(data=res.content, format="nt")
        self.assertEqualGraphs(g, got)

        # variation: use file extension
        res = self.get(self.baseurl + "1991:1469.nt")
        self.assertEqual(200, res.status_code)
        self.assertEqual("text/plain", res.headers['Content-Type'])
        got = Graph()
        got.parse(data=res.content, format="nt")
        self.assertEqualGraphs(g, got)

    def test_turtle(self):
        # transform test 5: accept: text/turtle -> RDF statements (in Turtle)
        g = Graph().parse(data=self.get(self.baseurl + "1991:1469.rdf").text)
        res = self.get(self.baseurl + "1991:1469",
                       headers={'Accept': 'text/turtle'})
        self.assertEqual(200, res.status_code)
        self.assertEqual("text/turtle", res.headers['Content-Type'])
        got = Graph().parse(data=res.content, format="turtle")
        self.assertEqualGraphs(g, got)

        # variation: use file extension
        res = self.get(self.baseurl + "1991:1469.ttl")
        self.assertEqual(200, res.status_code)
        self.assertEqual("text/turtle", res.headers['Content-Type'])
        got = Graph()
        got.parse(data=res.content, format="turtle")
        self.assertEqualGraphs(g, got)

    def test_json(self):
        # transform test 6: accept: application/json -> RDF statements (in JSON-LD)
        g = Graph().parse(data=self.get(self.baseurl + "1991:1469.rdf").text)
        res = self.get(self.baseurl + "1991:1469",
                       headers={'Accept': 'application/json'})
        self.assertEqual(200, res.status_code)
        self.assertEqual("application/json", res.headers['Content-Type'])
        got = Graph().parse(data=res.text, format="json-ld")
        self.assertEqualGraphs(g, got)

        # variation: use file extension
        res = self.get(self.baseurl + "1991:1469.json")
        self.assertEqual(200, res.status_code)
        self.assertEqual("application/json", res.headers['Content-Type'])
        got = Graph()
        got.parse(data=res.text, format="json-ld")
        self.assertEqualGraphs(g, got)

    def test_unacceptable(self):
        res = self.get(self.baseurl + "1991:1469",
                       headers={'Accept': 'application/pdf'})
        self.assertEqual(res.status_code, 406)
        self.assertEqual("text/html; charset=utf-8", res.headers['Content-Type'])

        # variation: unknown file extension should also be unacceptable
        res = self.get(self.baseurl + "1991:1469.pdf")
        self.assertEqual(res.status_code, 406)
        self.assertEqual("text/html; charset=utf-8", res.headers['Content-Type'])

    def test_extended_rdf(self):
        # extended test 6: accept: "/data" -> extended RDF statements
        g = Graph().parse(data=self.get(self.baseurl + "1991:1469/data.rdf").text)
        
        res = self.get(self.baseurl + "1991:1469/data",
                       headers={'Accept': 'application/rdf+xml'})
        self.assertEqual(200, res.status_code)
        self.assertEqual("application/rdf+xml", res.headers['Content-Type'])
        got = Graph().parse(data=res.text)
        self.assertEqualGraphs(g, got)

    def test_extended_ntriples(self):
        # extended test 7: accept: "/data" + "text/plain" -> extended
        # RDF statements in NTriples
        g = Graph().parse(data=self.get(self.baseurl + "1991:1469/data.rdf").text)
        res = self.get(self.baseurl + "1991:1469/data",
                     headers={'Accept': 'text/plain'})
        self.assertEqual(200, res.status_code)
        self.assertEqual("text/plain", res.headers['Content-Type'])
        got = Graph().parse(data=res.text, format="nt")
        self.assertEqualGraphs(g, got)
        # variation: use file extension
        res = self.get(self.baseurl + "1991:1469/data.nt")
        self.assertEqual(200, res.status_code)
        self.assertEqual("text/plain", res.headers['Content-Type'])
        got = Graph().parse(data=res.text, format="nt")
        self.assertEqualGraphs(g, got)

    def test_extended_turtle(self):
        # extended test 7: accept: "/data" + "text/turtle" -> extended
        # RDF statements in Turtle
        g = Graph().parse(data=self.get(self.baseurl + "1991:1469/data.rdf").text)
        res = self.get(self.baseurl + "1991:1469/data",
                     headers={'Accept': 'text/turtle'})
        self.assertEqual(200, res.status_code)
        self.assertEqual("text/turtle", res.headers['Content-Type'])
        got = Graph().parse(data=res.content, format="turtle")
        self.assertEqualGraphs(g, got)
        # variation: use file extension
        res = self.get(self.baseurl + "1991:1469/data.ttl")
        self.assertEqual(200, res.status_code)
        self.assertEqual("text/turtle", res.headers['Content-Type'])
        got = Graph().parse(data=res.content, format="turtle")
        self.assertEqualGraphs(g, got)

    def test_dataset_html(self):
        res = self.get(self.baseurl  + "dataset/sfs")
        self.assertTrue(res.status_code, 200)
        self.assertEqual("text/html; charset=utf-8", res.headers['Content-Type'])

    def test_dataset_html_param(self):
        res = self.get(self.baseurl  + "dataset/sfs?titel=P")
        self.assertTrue(res.status_code, 200)
        self.assertEqual("text/html; charset=utf-8", res.headers['Content-Type'])
        self.assertIn('Författningar som börjar på "P"', res.text)

    def test_dataset_ntriples(self):
        res = self.get(self.baseurl  + "dataset/sfs",
                       headers={'Accept': 'text/plain'})
        self.assertTrue(res.status_code, 200)
        self.assertEqual("text/plain", res.headers['Content-Type'])
        Graph().parse(data=res.text, format="nt")
        res = self.get(self.baseurl  + "dataset/sfs.nt")
        self.assertTrue(res.status_code, 200)
        self.assertEqual("text/plain", res.headers['Content-Type'])
        Graph().parse(data=res.text, format="nt")

    # NOTE: Converting the entire SFS dataset to different
    # representations and then parsing the result (twice for each
    # test) is costly -- maybe we could use eg the sitenews dataset
    # for this?
    def test_dataset_turtle(self):
        res = self.get(self.baseurl  + "dataset/sfs",
                       headers={'Accept': 'text/turtle'})
        self.assertTrue(res.status_code, 200)
        self.assertEqual("text/turtle", res.headers['Content-Type'])
        Graph().parse(data=res.text, format="turtle")
        res = self.get(self.baseurl  + "dataset/sfs.ttl")
        self.assertTrue(res.status_code, 200)
        self.assertEqual("text/turtle", res.headers['Content-Type'])
        Graph().parse(data=res.text, format="turtle")

    def test_dataset_xml(self):
        res = self.get(self.baseurl  + "dataset/sfs",
                       headers={'Accept': 'application/rdf+xml'})
        self.assertTrue(res.status_code, 200)
        self.assertEqual("application/rdf+xml", res.headers['Content-Type'])
        Graph().parse(data=res.text)
        res = self.get(self.baseurl  + "dataset/sfs.rdf")
        self.assertTrue(res.status_code, 200)
        self.assertEqual("application/rdf+xml", res.headers['Content-Type'])
        Graph().parse(data=res.text)


class TestAnnotations(TestLagen):

    def test_inbound_links(self):
        res = self.get(self.baseurl + "1998:204/data",
                       headers={'Accept': 'application/rdf+xml'})
        graph = Graph().parse(data=res.text, format="xml")
        resource = graph.resource(URIRef("https://lagen.nu/1998:204"))
        self.assertEqual(str(resource.value(DCTERMS.title)), "Personuppgiftslag (1998:204)")
        # TODO: assert something about inbound relations (PUF, DIFS,
        # prop 2005/06:44, some legal case)


class TestSearch(TestLagen):

    def totalhits(self, soup):
        return int(soup.find("h1").text.split()[0])
        
    def test_basic_search(self):
        # assert that left nav contains a number of results with at least x hits
        res = self.get(self.baseurl + "search/?q=personuppgift")
        soup = BeautifulSoup(res.text, "lxml")
        self.assertGreaterEqual(self.totalhits(soup), 14)
        nav = soup.find("nav", id="toc")
        for repo, minhits in (("dv", 3),
                              ("prop", 3),
                              ("myndfs", 2),
                              ("sou", 2),
                              ("ds", 1),
                              ("mediawiki", 1),
                              ("sfs", 1),
                              ("static", 1)):
            link = nav.find("a", href=re.compile("type=%s" % repo))
            self.assertIsNotNone(link, "Found no nav link of type=%s" % repo)
            hits = int(link.parent.span.text) # a <span class="badge pull-right">42</span>
            self.assertGreaterEqual(hits, minhits, "Expected more hits for %s" % repo)

    def test_faceted_search(self):
        totalhits = self.totalhits(BeautifulSoup(self.get(
            self.baseurl + "search/?q=personuppgift").text, "lxml"))
        soup = BeautifulSoup(self.get(self.baseurl + "search/?q=personuppgift&type=dv").text,
                             "lxml")
        self.assertLess(self.totalhits(soup), totalhits)
        # for some reason, this search keyword yields ghost hits when using faceting
        totalhits = self.totalhits(BeautifulSoup(self.get(
            self.baseurl + "search/?q=avtal").text, "lxml"))
        soup = BeautifulSoup(self.get(self.baseurl + "search/?q=avtal&type=dv").text,
                             "lxml")
        self.assertLess(self.totalhits(soup), totalhits)

        # go on and test that the facets in the navbar is as they should

    def test_sfs_title(self):
        soup = BeautifulSoup(self.get(self.baseurl + "search/?q=personuppgiftslag").text,
                             "lxml")
        # examine if the first hit is the SFS with that exact
        # title. NB: The SFS should rank above prop 1997/98:44 which
        # has the exact same title. We do this by boosting the sfs index.
        hit = soup.find("section", "hit")
        self.assertEqual(hit.b.a.get("href"), "/1998:204")
        

class TestAutocomplete(TestLagen):
    def test_basic_sfs(self):
        res = self.get(self.baseurl + "api/?q=3+§+personuppgiftslag&_ac=true",
                       headers={'Accept': 'application/json'})
        # returns eg [{'url': 'http://localhost:8080/1998:204#P3',
        #              'label': '3 § personuppgiftslagen',
        #              'desc': 'I denna lag används följande '
        #                      'beteckningar med nedan angiven...'},
        #             {'url': 'http://localhost:8080/dom/nja/2015s180',
        #              'desc': 'NJA 2015 s. 180', # NB! Is :identifier not :title
        #              'label': 'Lagring av personuppgifter '
        #                       '(domstols dagboksblad) i dator har'
        #                       ' ansetts inte omfattad av ...'}]
        self.assertEqual('application/json', res.headers['Content-Type'])
        hits = res.json()
        self.assertEqual(hits[0]['url'], self.baseurl + "1998:204#P3")
        self.assertTrue(hits[0]['desc'].startswith("I denna lag"))
        self.assertGreaterEqual(len(hits), 1) # "3 §
                                              # Personuppgiftslagen"
                                              # only matches one thing
                                              # ("personuppgiftslagen
                                              # 3" matches several)

    def test_shortform_sfs(self):
        res = self.get(self.baseurl + "api/?q=TF+2:&_ac=true",
                       headers={'Accept': 'application/json'})
        hits = res.json()
        self.assertEqual(hits[0]['url'], self.baseurl + "1949:105#K2P1")
        self.assertEqual(hits[0]['label'], "2 kap. 1 § Tryckfrihetsförordning (1949:105)")
        self.assertTrue(hits[0]['desc'].startswith("Till främjande av ett fritt meningsutbyte"))

    def test_incomplete_lawname(self):
        res = self.get(self.baseurl + "api/?q=personuppgiftsl&_ac=true",
                       headers={'Accept': 'application/json'})
        hits = res.json()
        self.assertEqual(hits[0]['url'], self.baseurl + "1998:204")
        self.assertEqual(hits[0]['label'], "Personuppgiftslag (1998:204)")

        res = self.get(self.baseurl + "api/?q=TRYCK&_ac=true", # check that case insensitivity works
                       headers={'Accept': 'application/json'})
        hits = res.json()
        self.assertEqual(hits[0]['url'], self.baseurl + "1949:105")
        self.assertEqual(hits[0]['label'], "Tryckfrihetsförordning (1949:105)")

    def test_basic_dv(self):
        res = self.get(self.baseurl + "api/?q=NJA+2015+s+1&_ac=true",
                       headers={'Accept': 'application/json'})
        hits = res.json()
        self.assertEqual(hits[0]['url'], self.baseurl + "dom/nja/2015s166") # FIXME: not first hit when tested against full dataset 
        self.assertEqual(hits[0]['label'], "NJA 2015 s. 166")
        self.assertEqual(hits[0]['desc'], "Brott mot tystnadsplikten enligt tryckfrihetsförordningen.")
        
    def test_basic_prop(self):
        res = self.get(self.baseurl + "api/?q=prop+1997&_ac=true",
                       headers={'Accept': 'application/json'})
        hits = res.json()
        self.assertEqual(hits[0]['url'], self.baseurl + "prop/1997/98:44") # FIXME: Not first hit when tested against full dataset 
        self.assertEqual(hits[0]['label'], "Prop. 1997/98:44")
        self.assertEqual(hits[0]['desc'], "Personuppgiftslag")

# this is a local test, don't need to run it if we're running the test
# suite against a remote server
@unittest.skipIf(os.environ.get("FERENDA_TESTURL"), "Testing remote server")
class TestACExpand(unittest.TestCase):

    def setUp(self):
        self.wsgiapp = WSGIApp(repos=[SFS(datadir="tng.lagen.nu/data")])

    def test_expand_shortname(self):
        self.assertEqual(self.wsgiapp.expand_partial_ref("TF"),
                         "https://lagen.nu/1949:105#K")

    def test_expand_chapters(self):
        self.assertEqual(self.wsgiapp.expand_partial_ref("TF 1"),
                         "https://lagen.nu/1949:105#K1")

    def test_expand_all_sections(self):
        self.assertEqual(self.wsgiapp.expand_partial_ref("TF 1:"),
                         "https://lagen.nu/1949:105#K1P")

    def test_expand_prefixed_sections(self):
        self.assertEqual(self.wsgiapp.expand_partial_ref("TF 1:1"),
                         "https://lagen.nu/1949:105#K1P1")

    def test_chapterless_expand_all_sections(self):
        self.assertEqual(self.wsgiapp.expand_partial_ref("PUL"),
                         "https://lagen.nu/1998:204#P")

    def test_chapterless_expand_prefixed_sections(self):
        self.assertEqual(self.wsgiapp.expand_partial_ref("PUL 3"),
                         "https://lagen.nu/1998:204#P3")

class TestKeywordToc(unittest.TestCase):
    maxDiff = None
    def makeitem(self, text):
        return [Link(text, uri="https://lagen.nu/begrepp/" + text.replace("»", "//").replace(" ", "_"))]

    def do_test(self, keywords, want):
        repo = LNKeyword()
        body = repo.toc_generate_page_body(map(self.makeitem, keywords), None)
        got = serialize(body[1])
        self.assertEqual(want, got)
        
        
    def test_prefix_segmentation(self):
        self.do_test(["Abc",
                      "Abd",
                      "Abe",
                      "Afg",
                      "Ahi",
                      "Ahj",
                      "Ahk"],
                      """<Div class="threecol">
  <H2>
    <str>Ab</str>
  </H2>
  <UnorderedList>
    <ListItem>
      <Link uri="https://lagen.nu/begrepp/Abc">Abc</Link>
    </ListItem><ListItem>
      <Link uri="https://lagen.nu/begrepp/Abd">Abd</Link>
    </ListItem><ListItem>
      <Link uri="https://lagen.nu/begrepp/Abe">Abe</Link>
    </ListItem>
  </UnorderedList>
  <H2>
    <str>Af</str>
  </H2>
  <UnorderedList>
    <ListItem>
      <Link uri="https://lagen.nu/begrepp/Afg">Afg</Link>
    </ListItem>
  </UnorderedList>
  <H2>
    <str>Ah</str>
  </H2>
  <UnorderedList>
    <ListItem>
      <Link uri="https://lagen.nu/begrepp/Ahi">Ahi</Link>
    </ListItem><ListItem>
      <Link uri="https://lagen.nu/begrepp/Ahj">Ahj</Link>
    </ListItem><ListItem>
      <Link uri="https://lagen.nu/begrepp/Ahk">Ahk</Link>
    </ListItem>
  </UnorderedList>
</Div>
""")
        

    def test_segmentation_casing(self):
        self.do_test(["Albanien",
                      "ALFA",
                      "Algolean"], """<Div class="threecol">
  <H2>
    <str>Al</str>
  </H2>
  <UnorderedList>
    <ListItem>
      <Link uri="https://lagen.nu/begrepp/Albanien">Albanien</Link>
    </ListItem><ListItem>
      <Link uri="https://lagen.nu/begrepp/ALFA">ALFA</Link>
    </ListItem><ListItem>
      <Link uri="https://lagen.nu/begrepp/Algolean">Algolean</Link>
    </ListItem>
  </UnorderedList>
</Div>
""")
    
    def test_nested(self):
        self.do_test(["Abc",
                      "Abc»D",
                      "Abc»D»Efg",
                      "Abc»D»Hij",
                      # Note that there is no "Abc»K" entry -- the test should create a non-linked "phantom" entry
                      "Abc»K»Lmn",
                      "Abc»K»Opq",
                      "Ars"],
                     """<Div class="threecol">
  <H2>
    <str>Ab</str>
  </H2>
  <UnorderedList>
    <ListItem>
      <Link uri="https://lagen.nu/begrepp/Abc">Abc</Link>
      <UnorderedList>
        <ListItem>
          <Link uri="https://lagen.nu/begrepp/Abc//D">D</Link>
          <UnorderedList>
            <ListItem>
              <Link uri="https://lagen.nu/begrepp/Abc//D//Efg">Efg</Link>
            </ListItem><ListItem>
              <Link uri="https://lagen.nu/begrepp/Abc//D//Hij">Hij</Link>
            </ListItem>
          </UnorderedList>
        </ListItem><ListItem>
          <str>K</str>
          <UnorderedList>
            <ListItem>
              <Link uri="https://lagen.nu/begrepp/Abc//K//Lmn">Lmn</Link>
            </ListItem><ListItem>
              <Link uri="https://lagen.nu/begrepp/Abc//K//Opq">Opq</Link>
            </ListItem>
          </UnorderedList>
        </ListItem>
      </UnorderedList>
    </ListItem>
  </UnorderedList>
  <H2>
    <str>Ar</str>
  </H2>
  <UnorderedList>
    <ListItem>
      <Link uri="https://lagen.nu/begrepp/Ars">Ars</Link>
    </ListItem>
  </UnorderedList>
</Div>
""")

    def test_nested_mixed(self):
        self.do_test(["Abc",
                      "Abc»D",
                      "Abf",
                      "Abf»G"],
                      """<Div class="threecol">
  <H2>
    <str>Ab</str>
  </H2>
  <UnorderedList>
    <ListItem>
      <Link uri="https://lagen.nu/begrepp/Abc">Abc</Link>
      <UnorderedList>
        <ListItem>
          <Link uri="https://lagen.nu/begrepp/Abc//D">D</Link>
        </ListItem>
      </UnorderedList>
    </ListItem><ListItem>
      <Link uri="https://lagen.nu/begrepp/Abf">Abf</Link>
      <UnorderedList>
        <ListItem>
          <Link uri="https://lagen.nu/begrepp/Abf//G">G</Link>
        </ListItem>
      </UnorderedList>
    </ListItem>
  </UnorderedList>
</Div>
""")


    def test_phantoms(self):
        self.do_test(["Alkoholdryck»Sprit",
                      "Allmän försäkring»Sjukpenninggrundande inkomst"],
                     """<Div class="threecol">
  <H2>
    <str>Al</str>
  </H2>
  <UnorderedList>
    <ListItem>
      <str>Alkoholdryck</str>
      <UnorderedList>
        <ListItem>
          <Link uri="https://lagen.nu/begrepp/Alkoholdryck//Sprit">Sprit</Link>
        </ListItem>
      </UnorderedList>
    </ListItem><ListItem>
      <str>Allmän försäkring</str>
      <UnorderedList>
        <ListItem>
          <Link uri="https://lagen.nu/begrepp/Allmän_försäkring//Sjukpenninggrundande_inkomst">Sjukpenninggrundande inkomst</Link>
        </ListItem>
      </UnorderedList>
    </ListItem>
  </UnorderedList>
</Div>
""")
        
    def test_threelevels_phantom(self):
        self.do_test(["Analysmetod",
                      "Analys»Principalkomponentanalys»Sensorisk analys"],
                     """<Div class="threecol">
  <H2>
    <str>An</str>
  </H2>
  <UnorderedList>
    <ListItem>
      <Link uri="https://lagen.nu/begrepp/Analysmetod">Analysmetod</Link>
    </ListItem><ListItem>
      <str>Analys</str>
      <UnorderedList>
        <ListItem>
          <str>Principalkomponentanalys</str>
          <UnorderedList>
            <ListItem>
              <Link uri="https://lagen.nu/begrepp/Analys//Principalkomponentanalys//Sensorisk_analys">Sensorisk analys</Link>
            </ListItem>
          </UnorderedList>
        </ListItem>
      </UnorderedList>
    </ListItem>
  </UnorderedList>
</Div>
""")


    def test_nested_wat(self):
        # Some corner cases that broke the previous version of
        # toc_generate_page_body_thread
        self.do_test(['Allmän försäkring»Sjukpenninggrundande inkomst',
                      'Allmän försäkring vårdbidrag',
                      'Allmän försäkring»Återbetalning av sjukpenning'],
                     """<Div class="threecol">
  <H2>
    <str>Al</str>
  </H2>
  <UnorderedList>
    <ListItem>
      <str>Allmän försäkring</str>
      <UnorderedList>
        <ListItem>
          <Link uri="https://lagen.nu/begrepp/Allmän_försäkring//Sjukpenninggrundande_inkomst">Sjukpenninggrundande inkomst</Link>
        </ListItem>
      </UnorderedList>
    </ListItem><ListItem>
      <Link uri="https://lagen.nu/begrepp/Allmän_försäkring_vårdbidrag">Allmän försäkring vårdbidrag</Link>
    </ListItem><ListItem>
      <str>Allmän försäkring</str>
      <UnorderedList>
        <ListItem>
          <Link uri="https://lagen.nu/begrepp/Allmän_försäkring//Återbetalning_av_sjukpenning">Återbetalning av sjukpenning</Link>
        </ListItem>
      </UnorderedList>
    </ListItem>
  </UnorderedList>
</Div>
""")

        self.do_test(['Allmän försäkring vårdbidrag',
                      'Allmän försäkring»Återbetalning av sjukpenning'],
                     """<Div class="threecol">
  <H2>
    <str>Al</str>
  </H2>
  <UnorderedList>
    <ListItem>
      <Link uri="https://lagen.nu/begrepp/Allmän_försäkring_vårdbidrag">Allmän försäkring vårdbidrag</Link>
    </ListItem><ListItem>
      <str>Allmän försäkring</str>
      <UnorderedList>
        <ListItem>
          <Link uri="https://lagen.nu/begrepp/Allmän_försäkring//Återbetalning_av_sjukpenning">Återbetalning av sjukpenning</Link>
        </ListItem>
      </UnorderedList>
    </ListItem>
  </UnorderedList>
</Div>
""")