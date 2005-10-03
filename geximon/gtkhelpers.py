"""Convenience classes for GTK."""

import gtk
import os
import gobject

class WrappedTextView(gtk.TextView):
    """A custom TextView widget.

    It is read-only and wrapping can be controlled through a context menu.
    """

    def __init__(self):
        gtk.TextView.__init__(self)
        self.set_editable(False)
        self.connect('populate-popup', self._populate_popup)

    def _populate_popup(self, textview, menu):
        wrapping_submenu = gtk.Menu()

        menuitem1 = gtk.RadioMenuItem(label=_("_None"), group=None)
        menuitem1.connect('activate', self._set_wrap_mode, gtk.WRAP_NONE)
        wrapping_submenu.add(menuitem1)
        menuitem2 = gtk.RadioMenuItem(label=_("_On characters"),
                group=menuitem1)
        menuitem2.connect('activate', self._set_wrap_mode, gtk.WRAP_CHAR)
        wrapping_submenu.add(menuitem2)
        menuitem3 = gtk.RadioMenuItem(label=_("_On words"), group=menuitem1)
        menuitem3.connect('activate', self._set_wrap_mode, gtk.WRAP_WORD)
        wrapping_submenu.add(menuitem3)

        mode = textview.get_wrap_mode()
        if mode == gtk.WRAP_NONE:
            menuitem1.set_active(True)
        elif mode == gtk.WRAP_CHAR:
            menuitem2.set_active(True)
        elif mode == gtk.WRAP_WORD:
            menuitem3.set_active(True)
        
        menuitem = gtk.MenuItem(_("_Wrapping"))
        menuitem.set_submenu(wrapping_submenu)
        menuitem.show_all()
        separator = gtk.SeparatorMenuItem()
        separator.show_all()
        menu.prepend(separator)
        menu.prepend(menuitem)
        return True

    def _set_wrap_mode(self, menuitem, wrap_mode):
        self.set_wrap_mode(wrap_mode)


class PopupWindow(gtk.Window):
    """A popup window.
    
    Contains a TextView to show some text."""

    def __init__(self, title, text):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title(title)

        textview = WrappedTextView()
        textview.set_editable(False)
        buffer = self.buffer = textview.get_buffer()
        buffer.set_text(text)
        monospace = buffer.create_tag()
        monospace.set_property('family', 'Monospace')
        buffer.apply_tag(monospace,
                buffer.get_start_iter(), buffer.get_end_iter())

        vbox = gtk.VBox()
        self.createMenuBar()
        vbox.pack_start(self.menubar, expand=False)
        vbox.pack_end(framed(scrolled(textview)))
        self.add(vbox)

        self.set_default_size(600, 400)

    def createMenuBar(self):
        ui_string = """<ui>
        <menubar name='menubar'>
          <menu action='FileMenu'>
	    <menuitem action='SaveAs'/>
	    <menuitem action='Close'/>
	  </menu>
	</menubar>
	</ui>"""

	ag = gtk.ActionGroup('WindowActions')
	actions = [
	  ('FileMenu', None, '_File'),
	  ('SaveAs', gtk.STOCK_SAVE_AS, '_Save As', '<control>S', 'Save As', self.saveToFile),
	  ('Close', gtk.STOCK_CLOSE, '_Close', '<control>W', 'Close', lambda *args: self.destroy()),
	  ]
	
        ag.add_actions(actions)
	self.ui = gtk.UIManager()
	self.ui.insert_action_group(ag, 0)
	self.ui.add_ui_from_string(ui_string)
	self.add_accel_group(self.ui.get_accel_group())
        self.menubar = self.ui.get_widget('/menubar')

    def saveToFile(self, *args):
        """Save the contents of the window to a text file."""
        filesel = gtk.FileSelection()
        filesel.run()
        filename = filesel.get_filename()
        filesel.destroy()

        if os.path.exists(filename):
            dialog = AlertDialog(self,
                  _("The file with that name already exists."
                    "If you continue, the contents of the file will "
                    "be overwritten."), query=True)
            response = dialog.ask()
            if not response:
                return

        bounds = self.buffer.get_bounds()
        text = self.buffer.get_text(*bounds)
        try:
            f = open(filename, 'w')
            f.truncate(0)
            f.write(text)
            f.close()
        except IOError, e:
            dialog = AlertDialog(self, _("An error has occured."),
                    _("The file at `%s` could not be written.\nError: %s")
                            % (filename, e.strerror), error=True)
            dialog.ask()
        else:
            dialog = AlertDialog(self, _("Text saved successfully."),
                    _("The data was successfully saved to `%s`.") % filename)
            dialog.ask()
 

class EntryDialog(gtk.Dialog):
    """An entry dialog.

    Shows a modal dialog with a label and an Entry field.
    """

    def __init__(self, main_window, title, label_text):
        gtk.Dialog.__init__(self,
                title=title,
                parent=main_window,
                flags=(gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT),
                buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                         gtk.STOCK_OK, gtk.RESPONSE_OK))
        self.set_resizable(False)
        self.set_border_width(12)
        self.vbox.set_spacing(12)

        label = gtk.Label(label_text)
        self.entry = gtk.Entry()
        self.entry.set_property('activates-default', True)
        label.set_mnemonic_widget(self.entry)
        
        hbox = gtk.HBox()
        hbox.set_border_width(6)
        hbox.set_spacing(12)
        hbox.pack_start(label)
        hbox.pack_end(self.entry)
        self.vbox.add(hbox)

        self.ok_button = self.action_area.get_children()[0]
        self.ok_button.set_flags(gtk.CAN_DEFAULT)
        self.ok_button.grab_default()

    def get_input(self):
        """Return user input.
        
        Return a string: the text the user has input into the Entry. If the
        user chooses Cancel, return an empty string.
        """
        self.show_all()
        response = self.run()
        text = self.entry.get_text()
        self.destroy()
        if response == gtk.RESPONSE_OK:
            return text
        else:
            return ""


class AlertDialog(gtk.MessageDialog):
    """An alert dialog.

    Asks the user for verification of some action or provides information.
    """

    def __init__(self, main_window, header, text, query=False, error=False):
        if query:
            buttons = gtk.BUTTONS_OK_CANCEL
            icon = gtk.MESSAGE_WARNING
        else:
            buttons = gtk.BUTTONS_OK
            icon = error and gtk.MESSAGE_ERROR or gtk.MESSAGE_INFO
        dlg_text = ('<span weight="bold" size="larger">%s</span>\n\n%s'
                        % (header, text))
        gtk.MessageDialog.__init__(self, main_window,
                (gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT),
                icon, buttons, dlg_text)
        self.label.set_property('use-markup', True)

    def ask(self):
        self.show_all()
        response = self.run()
        self.destroy()
        return (response == gtk.RESPONSE_OK)


class Timer:
    """A higher-level timer.

    The GTK timers are rather dumb - they cannot be stopped externally or their
    intervals changed. This class allows to do just that.
    """

    class TimerBackend:
        """A timer that can be stopped."""
        def __init__(self, interval, callback, paused=False):
            self._callback = callback
            self.cancelled = False
            self.paused = paused
            gobject.timeout_add(interval, self.hit)
        def hit(self):
            if not (self.paused or self.cancelled):
                self._callback()
            return not self.cancelled

    def __init__(self, interval, callback):
        self._interval = interval
        self._callback = callback
        self._timer = self.TimerBackend(interval, callback)
        self._paused = False

    def update_interval(self, new_interval):
        if self._interval != new_interval:
            self._timer.cancelled = True
            self._interval = new_interval
            self._timer = self.TimerBackend(
                    new_interval, self._callback, self._paused)

    def set_paused(self, paused):
        self._paused = paused
        self._timer.paused = paused


def show_help():
    """Open a help window."""
    import os
    helpfile = os.path.abspath('../doc/geximon.html')
    if not os.path.exists(helpfile):
        helpfile = '/usr/share/doc/geximon/geximon.html'
    (os.system('gnome-moz-remote file://%s' % helpfile) == 0) or \
        (os.system('mozilla file://%s' % helpfile) == 0) or \
        (os.system('see %s &' % helpfile) == 0)

# decorators

def scrolled(widget):
    """Wrap widget in a gtk.ScrolledWindow and return the scrolled window."""
    scrolled_window = gtk.ScrolledWindow()
    scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    scrolled_window.add(widget)
    return scrolled_window

def framed(widget):
    """Wrap widget in a gtk.Frame and return the frame."""
    frame = gtk.Frame()
    frame.set_shadow_type(gtk.SHADOW_IN)
    frame.add(widget)
    return frame
