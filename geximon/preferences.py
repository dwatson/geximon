"""Geximon application preferences."""

import os
import sys

try:
        import gtk
except RuntimeError, e:
        if str(e) == "could not open display":
                print "Could not connect to an X display"
                sys.exit()

import gobject
import ConfigParser

__metaclass__ = type


class Preferences:

    track_log = True
    wrap_log = gtk.WRAP_CHAR
    show_process_list = False
    show_plotter = True
    show_statusbar = True

    log_dir = '/var/log/exim'
    bin_dir = '/usr/sbin'
    exim_binary = 'exim'
    mainlog_name = 'mainlog'
    use_sudo = False
    use_ssh = False
    hostname = ''

    log_interval = 200 # this is not accessible in GUI
    queue_interval = 2000
    process_interval = 5000
    plotting_interval = 1000

    remember_sizes = True
    window_width = 600
    window_height = 500
    plot_area_height = 80
    divider_position = 200

    confirm_actions = True
    report_success = True
    show_delivery = False

    def __init__(self):
        self.config_filename = os.path.expanduser('~/.geximonrc')
        self.autodetect_version()
        self._callbacks = []

    def autodetect_version(self):
        """Check if using exim4 rather than v3, change paths accordingly."""
        if os.path.exists('/var/log/exim4'):
            self.log_dir = '/var/log/exim4'
        if os.path.exists('/usr/sbin/exim4'):
            self.exim_binary = 'exim4'
        if os.path.exists(os.path.join(self.log_dir, 'main.log')):
            self.mainlog_name = 'main.log'

    def load(self):
        """Load the preferences from a file."""
        parser = ConfigParser.ConfigParser()
        try:
            parser.read([self.config_filename])
        except ConfigParser.ParsingError, e:
            print >> sys.stderr, e
            return

        def load_value(section, attr, getter):
            try:
                setattr(self, attr, getter(section, attr))
            except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
                pass
            except ValueError, e:
                print >> sys.stderr, _("Invalid setting for %r in %s:") \
                                            % (attr, self.config_filename)
                print >> sys.stderr, e

        load_bool = lambda s, attr: load_value(s, attr, parser.getboolean)
        load_int = lambda s, attr: load_value(s, attr, parser.getint)
        load_str = lambda s, attr: load_value(s, attr, parser.get)

        load_bool('display', 'show_plotter')
        load_bool('display', 'show_statusbar')
        load_bool('display', 'track_log')
        load_str('display', 'wrap_log')
        self.wrap_log = gtk.WRAP_CHAR
        load_bool('display', 'show_process_list')

        load_str('paths', 'log_dir')
        load_str('paths', 'bin_dir')
        load_str('paths', 'exim_binary')
        load_str('paths', 'mainlog_name')
        load_bool('paths', 'use_sudo')
        load_bool('paths', 'use_ssh')
        load_str('paths', 'hostname')

        load_int('timers', 'log_interval')
        load_int('timers', 'queue_interval')
        load_int('timers', 'process_interval')
        load_int('timers', 'plotting_interval')

        load_bool('dimensions', 'remember_sizes')
        load_int('dimensions', 'window_width')
        load_int('dimensions', 'window_height')
        load_int('dimensions', 'plot_area_height')
        load_int('dimensions', 'divider_position')

        load_bool('popups', 'confirm_actions')
        load_bool('popups', 'report_success')
	load_bool('popups', 'show_delivery')

    def save(self):
        """Save the preferences to a file."""
        parser = ConfigParser.ConfigParser()

        parser.add_section('display')
        parser.set('display', 'show_plotter', self.show_plotter)
        parser.set('display', 'show_statusbar', self.show_statusbar)
        parser.set('display', 'track_log', self.track_log)
        parser.set('display', 'show_process_list', self.show_process_list)
        parser.set('display', 'wrap_log', self.wrap_log)

        parser.add_section('paths')
        parser.set('paths', 'log_dir', self.log_dir)
        parser.set('paths', 'bin_dir', self.bin_dir)
        parser.set('paths', 'exim_binary', self.exim_binary)
        parser.set('paths', 'mainlog_name', self.mainlog_name)
        parser.set('paths', 'use_sudo', self.use_sudo)
        parser.set('paths', 'use_ssh', self.use_ssh)
        parser.set('paths', 'hostname', self.hostname)

        parser.add_section('timers')
        parser.set('timers', 'log_interval', self.log_interval)
        parser.set('timers', 'queue_interval', self.queue_interval)
        parser.set('timers', 'process_interval', self.process_interval)
        parser.set('timers', 'plotting_interval', self.plotting_interval)

        parser.add_section('dimensions')
        parser.set('dimensions', 'remember_sizes', self.remember_sizes)
        parser.set('dimensions', 'window_width', self.window_width)
        parser.set('dimensions', 'window_height', self.window_height)
        parser.set('dimensions', 'plot_area_height', self.plot_area_height)
        parser.set('dimensions', 'divider_position', self.divider_position)

        parser.add_section('popups')
        parser.set('popups', 'confirm_actions', self.confirm_actions)
        parser.set('popups', 'report_success', self.report_success)
	parser.set('popups', 'show_delivery', self.show_delivery)

        file = open(self.config_filename, 'w')
        try:
            parser.write(file)
        finally:
            file.close()

    def subscribe(self, callback):
        """Subscribe a callback for change notification."""
        self._callbacks.append(callback)

    def notify(self):
        """Notify all subscribers that preferences have changed."""
        for callback in self._callbacks:
            callback(self)


class PreferencesDialog(gtk.Dialog):

    def __init__(self, main_window, prefs):
        gtk.Dialog.__init__(self,
                title=_("Preferences"),
                parent=main_window,
                flags=(gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT),
                buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                         gtk.STOCK_OK, gtk.RESPONSE_OK))
        self._main_window = main_window
        self.set_resizable(False)
        self.set_border_width(12)
        self.vbox.set_spacing(18)

        self._setup_path_settings(prefs)
        self._setup_timer_settings(prefs)
        self._setup_popup_settings(prefs)
        self._setup_ui_settings(prefs)

        ok_button = self.action_area.get_children()[0]
        ok_button.set_flags(gtk.CAN_DEFAULT)
        ok_button.grab_default()

    def _setup_path_settings(self, prefs):
        paths = self.newStyleFrame(_("Paths"))
        pathgroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)

        def packedPathEntry(description, value):
            label = gtk.Label(description)
            label.set_alignment(0.0, 0.5)
            label.set_use_underline(True)
            pathgroup.add_widget(label)
            entry = gtk.Entry()
            entry.set_text(value)
            entry.set_size_request(200, -1)
            entry.set_property('activates-default', True)
            label.set_mnemonic_widget(entry)
            hbox = gtk.HBox(spacing=6)
            hbox.pack_start(label)
            hbox.pack_end(entry)
            paths.pack_start(hbox)
            return entry

        self._log_dir= packedPathEntry(
                _("Exim _log directory:"), prefs.log_dir)
        self._mainlog_name = packedPathEntry(
                _("_Name of main log:"), prefs.mainlog_name)
        self._bin_dir = packedPathEntry(
                _("Path to exim _binaries:"), prefs.bin_dir)
        self._exim_binary = packedPathEntry(
                _("_Name of exim binary:"), prefs.exim_binary)

        self._use_sudo = gtk.CheckButton(_("Use _sudo"))
        if prefs.use_sudo:
            self._use_sudo.set_active(1)
        paths.pack_start(self._use_sudo)
        
        self._use_ssh = gtk.CheckButton(_("Use _ssh"))
        if prefs.use_ssh:
            self._use_ssh.set_active(1)
        paths.pack_start(self._use_ssh)
        
        self._hostname = packedPathEntry(_("Remote Hostname"), prefs.hostname)

    def _setup_timer_settings(self, prefs):
        timers = self.newStyleFrame(_("Update intervals"))
        timergroup = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)

        def packedTimerSpin(description, value, min, max, step):
            label = gtk.Label(description)
            label.set_alignment(0.0, 0.5)
            timergroup.add_widget(label)
            adj = gtk.Adjustment(float(value)/1000, min, max, step)
            spinner = gtk.SpinButton(adj, digits=1)
            spinner.set_size_request(60, -1)
            spinner.set_property('activates-default', True)
            hbox = gtk.HBox(spacing=6)
            hbox.pack_start(label, expand=False)
            hbox.pack_start(spinner, expand=False)
            hbox.pack_start(gtk.Label(_("seconds")), expand=False)
            timers.pack_start(hbox)
            return spinner

        self._queue_interval = packedTimerSpin(
                _("Queue display:"), prefs.queue_interval, 0.5, 60, 0.1)
        self._process_interval = packedTimerSpin(
                _("Process display:"), prefs.process_interval, 2, 60, 1)
        self._plotting_interval = packedTimerSpin(
                _("Plots:"), prefs.plotting_interval, 0.5, 60, 0.5)

    def _setup_ui_settings(self, prefs):
        ui = self.newStyleFrame(_("User interface"))

        self._remember_sizes = gtk.CheckButton(
                _("Remember window size between sessions."))
        self._remember_sizes.set_active(prefs.remember_sizes)
        ui.pack_start(self._remember_sizes)

        # set up the plot area height spinner
        adj = gtk.Adjustment(prefs.plot_area_height, 40, 2000, 5)
        spinner = gtk.SpinButton(adj, digits=0)
        spinner.set_size_request(60, -1)
        spinner.set_property('activates-default', True)

        def valueChanged(spinbutton, prefs):
            prefs.plot_area_height = spinbutton.get_value_as_int()
            prefs.notify()
        spinner.connect('value-changed', valueChanged, prefs)
        
        hbox = gtk.HBox(spacing=6)
        hbox.pack_start(gtk.Label(_("Plot area height:")), expand=False)
        hbox.pack_start(spinner, expand=False)
        hbox.pack_start(gtk.Label(_("pixels")), expand=False)
        ui.pack_start(hbox)
        self._plot_area_height = spinner

    def _setup_popup_settings(self, prefs):
        popups = self.newStyleFrame(_("Popup messages"))

        self._confirm_actions = gtk.CheckButton(
                _("Confirm dangerous actions"))
        self._confirm_actions.set_active(prefs.confirm_actions)
        popups.pack_start(self._confirm_actions)

        self._report_success = gtk.CheckButton(
                _("Show a popup report after successful actions"))
        self._report_success.set_active(prefs.report_success)
        popups.pack_start(self._report_success)

	self._show_delivery = gtk.CheckButton(
	        _("Show verbose delivery of single messages"))
	self._show_delivery.set_active(prefs.show_delivery)
	popups.pack_start(self._show_delivery)

    def newStyleFrame(self, title):
        """Create a HIG-compliant "frame".

        Returns the content vbox.
        """
        title = gtk.Label('<span weight="bold">%s</span>' % title)
        title.set_property('use-markup', True)
        title.set_alignment(0.0, 0.5)

        content = gtk.VBox(spacing=6)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(' ' * 4), expand=False)
        hbox.pack_end(content)

        vbox = gtk.VBox()
        vbox.set_spacing(12)
        vbox.pack_start(title)
        vbox.pack_end(hbox)
        self.vbox.add(vbox)

        return content

    def apply(self, prefs):
        """Store settings in prefs."""

        prefs.bin_dir = self._bin_dir.get_text()
        prefs.exim_binary = self._exim_binary.get_text()
        prefs.use_sudo = self._use_sudo.get_active()
        prefs.use_ssh = self._use_ssh.get_active()
        prefs.hostname = self._hostname.get_text()
        prefs.log_dir = self._log_dir.get_text()
        prefs.mainlog_name = self._mainlog_name.get_text()

        prefs.queue_interval = \
                int(self._queue_interval.get_value() * 1000)
        prefs.process_interval = \
                int(self._process_interval.get_value() * 1000)
        prefs.plotting_interval = \
                int(self._plotting_interval.get_value() * 1000)

        prefs.confirm_actions = bool(self._confirm_actions.get_active())
        prefs.report_success = bool(self._report_success.get_active())

        prefs.remember_sizes = bool(self._remember_sizes.get_active())
        prefs.plot_area_height = self._plot_area_height.get_value_as_int()

        prefs.save()
        prefs.notify()
