# -*- coding: utf-8 -*-
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
from builtins import *

import sys
import os

from ferenda.compat import unittest, patch, MagicMock
from ferenda import util


# SUT
from ferenda import PDFReader
from ferenda import PDFAnalyzer


@unittest.skipIf (sys.version_info < (2, 7, 0),
                  "PDFAnalyzer not currently supported under Py26")
class Analyze(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.pdf = PDFReader(filename="test/files/pdfanalyze/lipsum.pdf",
                             workdir="test/files/pdfanalyze/")
        self.analyzer = PDFAnalyzer(self.pdf)

    def test_documents(self):
        self.assertEquals([(0,3, 'main')], self.analyzer.documents)

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
        stylecounter = self.analyzer.count_styles(1, 2)
        self.assertEquals(dict(stylecounter),
                          {('Comic Sans MS', 14): 5922,
                           ('Cambria,Bold', 14): 133,
                           ('Cambria,Bold', 17): 128,
                           ('Cambria,Bold', 19): 61})

    def test_analyze_hmargins(self):
        hcounters = self.analyzer.count_horizontal_margins(0, 3)
        hmetrics = self.analyzer.analyze_horizontal_margins(hcounters)
        self.assertEqual({'leftmargin': 135,
                           'leftmargin_even': 108,
                           'pagewidth': 892,
                           'rightmargin': 780,
                           'rightmargin_even': 760},
                          hmetrics)

    def test_analyze_vmargins(self):
        vcounters = self.analyzer.count_vertical_margins(0, 3)
        vmetrics = self.analyzer.analyze_vertical_margins(vcounters)
        # this will miscalculate the header zone because the header is
        # so wordy it's considered part of the main document text
        self.assertEquals(vmetrics, {'bottommargin': 1149, 'pageheight': 1262, 'topmargin': 53})

        # try again with double the thresholds
        self.analyzer.header_significance_threshold = 0.004
        vmetrics = self.analyzer.analyze_vertical_margins(vcounters)
        self.assertEquals(vmetrics, {'bottommargin': 1149, 'pageheight': 1262, 'topmargin': 107})

    def test_analyze_styles(self):
        stylecounter = self.analyzer.count_styles(1, 3)
        stylemetrics = self.analyzer.analyze_styles(stylecounter)
        self.assertEquals({'default': {'family': 'Comic Sans MS', 'size': 14},
                           'h1': {'family': 'Cambria,Bold', 'size': 19},
                           'h2': {'family': 'Cambria,Bold', 'size': 17},
                           'h3': {'family': 'Cambria,Bold', 'size': 14}},
                          stylemetrics)

    # this is more of a functional test
    def test_margins(self):
        jsonpath = "test/files/pdfanalyze/lipsum.metrics.json"
        try:
            self.assertFalse(os.path.exists(jsonpath))
            metrics = self.analyzer.metrics(jsonpath, startpage=1)
            self.assertEquals({'default': {'family': 'Comic Sans MS', 'size': 14},
                               'bottommargin': 1149,
                               'h1': {'family': 'Cambria,Bold', 'size': 19},
                               'h2': {'family': 'Cambria,Bold', 'size': 17},
                               'h3': {'family': 'Cambria,Bold', 'size': 14},
                               'topmargin': 53,
                               'leftmargin': 135,
                               'leftmargin_even': 108,
                               'pageheight': 1262,
                               'pagewidth': 892,
                               'rightmargin': 780,
                               'rightmargin_even': 760,
                               'scanned_source': False},
                              metrics)
            self.assertTrue(os.path.exists(jsonpath))
        finally:
            util.robust_remove(jsonpath)

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
                           'pageheight': 1262,
                           'pagewidth': 892,
                           'rightmargin_even': 760,
                           'scanned_source': False},
                          metrics)

    def test_plot(self):
        matplotmock = MagicMock()
        mocks = {'matplotlib': matplotmock,
                 'matplotlib.pyplot': MagicMock()}
        with patch.dict('sys.modules', mocks):
            self.analyzer.metrics(plotpath="foo/bar/baz")
            self.assertTrue(matplotmock.pyplot.savefig.called)

    def test_drawboxes(self):
        pypdfmock = MagicMock()
        canvasmock = MagicMock()
        mocks = {'PyPDF2': pypdfmock,
                 'reportlab': MagicMock(),
                 'reportlab.pdfgen': MagicMock(),
                 'reportlab.pdfgen.canvas': canvasmock}
        with patch.dict('sys.modules', mocks):
            metrics = self.analyzer.metrics()
            pdfpath = "test/files/pdfanalyze/lipsum.debug.pdf"
            self.analyzer.drawboxes(pdfpath, metrics=metrics)
        self.assertTrue(canvasmock.Canvas.called)
        self.assertTrue(pypdfmock.PdfFileReader.called)
        self.assertTrue(pypdfmock.PdfFileWriter.called)
        util.robust_remove(pdfpath)
