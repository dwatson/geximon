#!/usr/bin/env python
"""Geximon unit testing module."""

import unittest
import doctest

import sys
sys.path.insert(0, '..')

class TestWindows(unittest.TestCase):

    def test_createGEximonWindow(self):
        from geximon.geximon import GEximonWindow
        win = GEximonWindow()

    def test_createProcessWindow(self):
        from geximon.geximon import ProcessWindow
        from geximon.preferences import Preferences
        prefs = Preferences()
        w = ProcessWindow(prefs)

    def test_createPopupWindow(self):
        from geximon.widgets import PopupWindow
        w = PopupWindow("title", "text")


class TestPreferences(unittest.TestCase):

    def test_createDialog(self):
        from geximon.preferences import Preferences, PreferencesDialog
        prefs = Preferences()
        dlg = PreferencesDialog(None, prefs)


if __name__ == '__main__':
    suite = unittest.TestSuite()

    from geximon import exim
    suite.addTest(doctest.DocTestSuite(exim))

    suite.addTest(unittest.makeSuite(TestWindows))
    suite.addTest(unittest.makeSuite(TestPreferences))
    unittest.TextTestRunner(verbosity=2).run(suite)
