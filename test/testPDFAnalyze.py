# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys, os, tempfile, shutil
from lxml import etree
from ferenda.compat import unittest
if os.getcwd() not in sys.path: sys.path.insert(0,os.getcwd())

from bz2 import BZ2File
from ferenda import errors, util
from six import text_type as str

from ferenda import PDFReader

# SUT
from ferenda import PDFAnalyzer

@unittest.skipIf (sys.version_info < (2, 7, 0), "PDFAnalyzer not currently supported under Py26")
class Analyze(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.pdf = PDFReader(filename="test/files/pdfanalyze/lipsum.pdf",
                             workdir="test/files/pdfanalyze/")
        self.analyzer = PDFAnalyzer(self.pdf)

    def tearDown(self):
        util.robust_remove("test/files/pdfanalyze/lipsum.metrics.json")
        util.robust_remove("test/files/pdfanalyze/lipsum.plot.png")
        util.robust_remove("test/files/pdfanalyze/lipsum.debug.pdf")

    def test_documents(self):
        self.assertEquals([(0,3)], self.analyzer.documents())

    def test_vcounters(self):
        vcounters = self.analyzer.count_vertical_margins(0, 3)
        self.assertEquals(set(vcounters.keys()),
                          set(('bottommargin', 'topmargin', 'pageheight')))
        self.assertEquals(max(vcounters['pageheight']), 1262)
        self.assertEquals(vcounters['bottommargin'][76], 22) # charcount of topmargins from 2 pages
        self.assertEquals(vcounters['topmargin'][1167], 3) # pagenumbers on 3 pages 
        
    def test_hcounters(self):
        hcounters = self.analyzer.count_horizontal_margins(0, 3)
        self.assertEquals(set(hcounters.keys()),
                          set(('leftmargin', 'rightmargin', 'leftmargin_even', 'rightmargin_even', 'pagewidth')))
        self.assertEquals(set(hcounters['leftmargin'].keys()), set((135, 775, 778))) # 775, 778 are pagenumbers on pg 1 + 3
        self.assertEquals(list(hcounters['leftmargin_even'].keys()), [108])
        self.assertEquals(hcounters['rightmargin'].most_common(1)[0][0], 784)

    def test_stylecounters(self):
        stylecounters = self.analyzer.count_styles(0, 3)
        self.assertEquals(dict(stylecounters['frontmatter_styles']),
                          {('Comic Sans MS', 14): 2150,
                           ('Cambria,Bold', 14): 68,
                           ('Cambria,Bold', 17): 64,
                           ('Cambria', 37): 55,
                           ('Cambria,Bold', 19): 28})
        self.assertEquals(dict(stylecounters['rest_styles']),
                          {('Comic Sans MS', 14): 5922,
                           ('Cambria,Bold', 14): 133,
                           ('Cambria,Bold', 17): 128,
                           ('Cambria,Bold', 19): 61})

    def test_analyze_hmargins(self):
        hcounters = self.analyzer.count_horizontal_margins(0, 3)
        hmetrics = self.analyzer.analyze_horizontal_margins(hcounters)
        self.assertEquals({'leftmargin': 135,
                           'leftmargin_even': 108,
                           'pagewidth': 892,
                           'rightmargin': 784,
                           'rightmargin_even': 748},
                          hmetrics)

    def test_analyze_vmargins(self):
        vcounters = self.analyzer.count_vertical_margins(0, 3)
        vmetrics = self.analyzer.analyze_vertical_margins(vcounters)
        # this will miscalculate the header zone because the header is
        # so wordy it's considered part of the main document text
        self.assertEquals(vmetrics, {'bottommargin': 1149, 'topmargin': 53})

        # try again with double the thresholds
        self.analyzer.header_significance_threshold = 0.004
        vmetrics = self.analyzer.analyze_vertical_margins(vcounters)
        self.assertEquals(vmetrics, {'bottommargin': 1149, 'topmargin': 107})

    def test_analyze_styles(self):
        stylecounters = self.analyzer.count_styles(0, 3)
        stylemetrics = self.analyzer.analyze_styles(stylecounters['frontmatter_styles'],
                                                    stylecounters['rest_styles'])
        self.assertEquals({'default': {'family': 'Comic Sans MS', 'size': 14},
                           'h1': {'family': 'Cambria,Bold', 'size': 19},
                           'h2': {'family': 'Cambria,Bold', 'size': 17},
                           'h3': {'family': 'Cambria,Bold', 'size': 14},
                           'title': {'family': 'Cambria', 'size': 37}},
                          stylemetrics)

    # this is more of a functional test
    def test_margins(self):
        jsonpath = "test/files/pdfanalyze/lipsum.metrics.json"
        self.assertFalse(os.path.exists(jsonpath))
        metrics = self.analyzer.metrics(jsonpath)
        self.assertEquals({'default': {'family': 'Comic Sans MS', 'size': 14},
                           'bottommargin': 1149,
                           'h1': {'family': 'Cambria,Bold', 'size': 19},
                           'h2': {'family': 'Cambria,Bold', 'size': 17},
                           'h3': {'family': 'Cambria,Bold', 'size': 14},
                           'topmargin': 53,
                           'leftmargin': 135,
                           'leftmargin_even': 108,
                           'pagewidth': 892,
                           'rightmargin': 784,
                           'rightmargin_even': 748,
                           'title': {'family': 'Cambria', 'size': 37}},
                          metrics)
        self.assertTrue(os.path.exists(jsonpath))

    def test_margins_subdocument(self):
        self.analyzer.frontmatter = 0
        # note that this will only analyze a single even page
        metrics = self.analyzer.metrics(startpage=1, pagecount=1)
        self.assertEquals({'default': {'family': 'Comic Sans MS', 'size': 14},
                           'bottommargin': 1149,
                           'h1': {'family': 'Cambria,Bold', 'size': 19},
                           'h2': {'family': 'Cambria,Bold', 'size': 17},
                           'h3': {'family': 'Cambria,Bold', 'size': 14},
                           'topmargin': 53,
                           'leftmargin_even': 108,
                           'pagewidth': 892,
                           'rightmargin_even': 748},
                          metrics)

    @unittest.skipIf('TRAVIS' in os.environ or 'APPVEYOR' in os.environ, "Not using matplotlib-based tests on Travis/Appveyor")
    def test_plot(self):
        # just test that a plot is created
        plotpath = "test/files/pdfanalyze/lipsum.plot.png"
        self.assertFalse(os.path.exists(plotpath))
        self.analyzer.metrics(plotpath=plotpath)
        self.assertTrue(os.path.exists(plotpath))

    # reportlab doesn't work with py3.2, current release of pyPDF2
    # (1.24) has a py3 bug that crashes page merging (patch exists at
    # https://github.com/mstamy2/PyPDF2/pull/172)
    @unittest.skipIf(sys.version_info > (3, 0, 0) or 'TRAVIS' in os.environ or 'APPVEYOR' in os.environ, "pyPDF2 not working on py3")
    def test_drawboxes(self):
        # just test that a pdf is created
        pdfpath = "test/files/pdfanalyze/lipsum.debug.pdf"
        self.assertFalse(os.path.exists(pdfpath))
        metrics = self.analyzer.metrics()
        self.analyzer.drawboxes(pdfpath, metrics=metrics)
        self.assertTrue(os.path.exists(pdfpath))
