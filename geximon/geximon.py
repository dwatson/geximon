#!/usr/bin/env python
"""
    Copyright (C) 2004  Gintautas Miliauskas <gintas@pov.lt>,
                        Programmers of Vilnius

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
"""

VERSION = "0.7"

import gettext
gettext.install('geximon')

import gtk
import gobject

from exim import LogWatcher, QueueManager
from gtkhelpers import AlertDialog
from gtkhelpers import framed, scrolled, show_help
from widgets import LogWidget, ProcessWidget, QueueWidget
from widgets import PopupWindow, ExigrepDialog, EximstatsDialog
from preferences import Preferences, PreferencesDialog
from plotter import Plotter


class GEximonWindow(gtk.Window):
    """The main geximon window."""

    def __init__(self):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title('gEximon')
        self.connect('delete-event', self.quit)

        self.prefs = prefs = Preferences()
        prefs.load()
        prefs.subscribe(self.apply_prefs)

        self.logwatcher = LogWatcher(prefs.log_dir, prefs.mainlog_name,
                prefs.bin_dir, prefs.use_sudo)

        # callback is None, it will be specified by QueueWidget
        self.queue_mgr = QueueManager(None,
                prefs.bin_dir, prefs.exim_binary, prefs.use_sudo)

        self._setUpIcons()

        # create menu bar
        self._setUpMenu()

        # create status bar
        self.statusbar = gtk.Statusbar()
        self.statusbar.push(0, '')

        # set up widgets
        self.plotter = Plotter(self.logwatcher, self.queue_mgr, prefs)
        self.log_widget = LogWidget(self.logwatcher, prefs)
        self.queue_widget = QueueWidget(self,
                self.logwatcher, self.queue_mgr, prefs)

        self.process_window = ProcessWindow(prefs)
        def processWindowClosed(*ignored_arguments):
            self.prefs.show_process_list = False
            self.prefs.notify()
            return True # prevent the window from getting destroyed
        self.process_window.connect('delete-event', processWindowClosed)

        self._layOutWidgets()
        prefs.notify()

    def _setUpIcons(self):
        try:
            icon16x16 = gtk.gdk.pixbuf_new_from_file(
                    '/usr/share/pixmaps/geximon-16x16.xpm')
            icon32x32 = gtk.gdk.pixbuf_new_from_file(
                    '/usr/share/pixmaps/geximon-32x32.xpm')
        except gobject.GError:
            pass
        else:
            gtk.window_set_default_icon_list(icon32x32, icon16x16)

    def _setUpMenu(self):
        """Set up the main menubar."""

        def runQueue(*ignored_arguments):
            self.queue_mgr.runQueue()
            if self.prefs.report_success:
                AlertDialog(self, _("A queue runner has been started."),
                    _("A new exim instance has been started in the background."
                      " It will process the queue and then terminate."))

        def runExigrep(*ignored_arguments):
            dialog = ExigrepDialog(self)
            dialog.go(self.logwatcher)

        def runEximstats(*ignored_arguments):
            dialog = EximstatsDialog(self)
            dialog.go(self.logwatcher)

        def getRejectlog(*ignored_arguments):
            text = self.logwatcher.getRejectlog()
            PopupWindow(_("Reject log"), text).show_all()

        def getConfig(*ignored_arguments):
            text = self.queue_mgr.getConfiguration()
            PopupWindow(_("Exim configuration"), text).show_all()

        def scrollLogToggled(action, menuitem):
            """Automatically scroll the log on new data."""
            self.prefs.track_log = menuitem.get_active()
            self.prefs.notify()

        def processDisplayToggled(action, menuitem):
            """Show or hide the process list window."""
            self.prefs.show_process_list = menuitem.get_active()
            self.prefs.notify()

        def plotDisplayToggled(action, menuitem):
            """Show or hide the plot area."""
            self.prefs.show_plotter = menuitem.get_active()
            self.prefs.notify()

        def statusbarDisplayToggled(action, menuitem):
            """Show or hide the statusbar."""
            self.prefs.show_statusbar = menuitem.get_active()
            self.prefs.notify()

        def helpContents(action, menuitem):
            """Show the help contents."""
            show_help()

        accel_group = gtk.AccelGroup()
        item_factory = gtk.ItemFactory(gtk.MenuBar, "<main>", accel_group)
        item_factory.create_items([
                (_("/_Geximon"), None, None, 1, '<Branch>'),
                (_("/Geximon/<tearoff>"), None, None, 0, '<Tearoff>'),
                (_("/Geximon/_Preferences"), '<control>P',
                    self.editPreferences,
                    10, '<StockItem>', gtk.STOCK_PREFERENCES),
                (_("/Geximon/<sep1>"), None, None, 0, '<Separator>'),
                (_("/Geximon/_Quit"), '<control>Q', self.quit,
                    11, '<StockItem>', gtk.STOCK_QUIT),
                (_("/_Exim"), None, None, 2, '<Branch>'),
                (_("/Exim/<tearoff>"), None, None, 0, '<Tearoff>'),
                (_("/Exim/Spawn _Queue Runner"), '<control>R', runQueue, 20,
                    None),
                (_("/Exim/<sep1>"), None, None, 0, '<Separator>'),
                (_("/Exim/Exi_grep"), None, runExigrep, 21, None),
                (_("/Exim/Exim_stats"), None, runEximstats, 22, None),
                (_("/Exim/<sep2>"), None, None, 0, '<Separator>'),
                (_("/Exim/See _Rejectlog"), None, getRejectlog, 23, None),
                (_("/Exim/<sep3>"), None, None, 0, '<Separator>'),
                (_("/Exim/Get _Configuration"), None, getConfig, 23, None),
                (_("/_View"), None, None, 30, '<Branch>'),
                (_("/View/<tearoff>"), None, None, 0, '<Tearoff>'),
                (_("/View/_Plots"), '<control>G', plotDisplayToggled,
                    31, "<CheckItem>"),
                (_("/View/_Statusbar"), None, statusbarDisplayToggled,
                    32, "<CheckItem>"),
                (_("/View/<sep1>"), None, None, 0, '<Separator>'),
                (_("/View/_Process List"), '<control>L', processDisplayToggled,
                    33, "<CheckItem>"),
                (_("/View/<sep2>"), None, None, 0, '<Separator>'),
                (_("/View/_Scroll log on new data"), '<control>S',
                    scrollLogToggled, 34, "<CheckItem>"),
                (_("/_Help"), None, None, 90, '<LastBranch>'),
                (_("/Help/<tearoff>"), None, None, 0, '<Tearoff>'),
                (_("/Help/_Contents"), None, helpContents, 91, None),
                (_("/Help/_About"), None, self.about, 92, None),
                ])
        self.add_accel_group(accel_group)
        self.menubar = item_factory.get_widget('<main>')

        self.show_plotter_menu_item = item_factory.get_item_by_action(31)
        self.show_statusbar_menu_item = item_factory.get_item_by_action(32)
        self.process_list_menu_item = item_factory.get_item_by_action(33)
        self.track_log_menu_item = item_factory.get_item_by_action(34)

        # need to store the reference so it doesn't get garbage collected
        self._item_factory = item_factory

    def _layOutWidgets(self):
        self.pane = gtk.VPaned()
        self.pane.pack1(framed(scrolled(self.log_widget)), resize=True)
        self.pane.pack2(framed(scrolled(self.queue_widget)), resize=True)

        self.vbox = gtk.VBox()
        self.vbox.set_border_width(2)
        self.vbox.pack_start(framed(self.plotter), expand=False)
        self.vbox.pack_end(self.pane)

        self.vbox2 = gtk.VBox()
        self.vbox2.pack_start(self.menubar, expand=False)
        self.vbox2.pack_start(self.vbox, expand=True)
        self.vbox2.pack_end(self.statusbar, expand=False)
        self.add(self.vbox2)
        if self.prefs.remember_sizes:
            self.set_default_size(
                    self.prefs.window_width, self.prefs.window_height)
            self.pane.set_position(self.prefs.divider_position)
        else:
            self.set_default_size(550, 600)

    def quit(self, *ignored_arguments):
        self.save_preferences()
        # it would be nice if the following were called automatically
        self.process_window.process_widget.cleanup()
        gtk.mainquit()
        return False

    def save_preferences(self):
        self.prefs.window_width, self.prefs.window_height = self.get_size()
        self.prefs.divider_position = self.pane.get_position()
        self.prefs.wrap_log = self.log_widget.get_wrap_mode()
        self.prefs.save()

    def about(self, *ignored_arguments):
        """Show the about dialog."""
        about_dialog = AboutDialog(self)
        about_dialog.go()

    def editPreferences(self, *ignored_arguments):
        """Show the preferences dialog."""
        pref_dialog = PreferencesDialog(self, self.prefs)
        pref_dialog.show_all()
        response = pref_dialog.run()
        if response == gtk.RESPONSE_OK:
            pref_dialog.apply(self.prefs)
        pref_dialog.hide()

    def apply_prefs(self, prefs):
        self.process_list_menu_item.set_active(prefs.show_process_list)
        self.show_plotter_menu_item.set_active(prefs.show_plotter)
        self.show_statusbar_menu_item.set_active(prefs.show_statusbar)
        if prefs.show_statusbar:
            self.statusbar.show_all()
        else:
            self.statusbar.hide()
        self.track_log_menu_item.set_active(prefs.track_log)


class ProcessWindow(gtk.Window):
    """A window that contains the exim process list."""

    def __init__(self, prefs):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_default_size(500, 200)
        self.set_title(_("Exim processes"))

        self.statusbar = gtk.Statusbar()
        self.statusbar.push(0, '')
        self.process_widget = ProcessWidget(self.statusbar, prefs)

        vbox = gtk.VBox()
        vbox.pack_start(scrolled(self.process_widget))
        vbox.pack_end(self.statusbar, expand=False)

        self.add(framed(vbox))

        prefs.subscribe(self.apply_prefs)

    def apply_prefs(self, prefs):
        if prefs.show_process_list:
            self.process_widget.update()
            self.show_all()
        else:
            self.hide()


class AboutDialog(gtk.Dialog):
    """The About dialog."""

    def __init__(self, main_window):
        gtk.Dialog.__init__(self, _("About gEximon"), main_window,
                flags=(gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT),
                buttons=(gtk.STOCK_OK, gtk.RESPONSE_OK))
        self.set_resizable(False)
        self.set_border_width(12)
        self.vbox.set_spacing(18)

        text = '<span weight="bold" size="larger">gEximon v%s</span>' % VERSION
        title = gtk.Label(text)
        title.set_property('use-markup', True)
        self.vbox.add(title)

        text = _("A GNOME monitor for the exim mail transport agent.")
        about = gtk.Label(text)
        self.vbox.add(about)

        text = ("<i>" + _("Author") + ": " +
                "Gintautas Miliauskas &lt;gintas@pov.lt&gt;\n" +
                "Programmers of Vilnius, 2004</i>")
        author = gtk.Label(text)
        author.set_property('use-markup', True)
        self.vbox.add(author)

    def go(self):
        self.show_all()
        self.run()
        self.destroy()


def main():
    mainwin = GEximonWindow()
    mainwin.show_all()

    # XXX these should be moved somewhere else
    if not mainwin.prefs.show_plotter:
        mainwin.plotter.set_visible(False)
    if not mainwin.prefs.show_statusbar:
        mainwin.statusbar.hide()
    gtk.gdk.threads_init()
    gtk.main()


if __name__ == '__main__':
    main()
