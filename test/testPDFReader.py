# -*- coding: utf-8 -*-
from __future__ import unicode_literals

# NOTE: This unittest requires that the pdftohtml binary is available
# and calls that, making this not a pure unittest.

import sys, os, tempfile, shutil
from lxml import etree
from ferenda.compat import unittest
if os.getcwd() not in sys.path: sys.path.insert(0,os.getcwd())

# SUT
from ferenda import PDFReader

class Read(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None
        self.datadir = tempfile.mkdtemp()
        self.reader = PDFReader()
        
    def tearDown(self):
        shutil.rmtree(self.datadir)

    def test_basic(self):
        self.reader.read("test/files/pdfreader/sample.pdf",
                         self.datadir)
        self.assertEqual(len(self.reader), 1)
        # first page, first box
        title = str(self.reader[0][0])
        self.assertEqual(title, "Document title")