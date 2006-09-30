"""Widgets for Geximon"""

import sys
import os
import datetime
import signal
import re   # needed to escape exigrep patterns

try:
        import gtk
except RuntimeError, e:
        if str(e) == "could not open display":
                print "Could not connect to an X display"
                sys.exit()

import gobject

from exim import ProcessManager, QueueManager
from gtkhelpers import Timer, WrappedTextView
from gtkhelpers import PopupWindow, EntryDialog, AlertDialog

__metaclass__ = type


class LogWidget(WrappedTextView):
    """A widget that displays the tail of the exim main log."""

    MAX_LOG_LINES = 10000 # maximum lines to have in the buffer at a time

    def __init__(self, logwatcher, prefs):
        WrappedTextView.__init__(self)
        self._track_log = prefs.track_log
        prefs.subscribe(self.apply_prefs)

        self._logwatcher = logwatcher

        self.buffer = self.get_buffer()
        self.buffer.create_tag('monospace', family='Monospace')
        self.buffer.create_tag('time', foreground='purple')
        self.buffer.create_tag('message_id', foreground='blue')
        self.buffer.create_tag('info', foreground='black')

        self.buffer.create_mark('end', self.buffer.get_end_iter(), False)

        self.buffer.insert_with_tags_by_name(self.buffer.get_start_iter(),
                _("geximon started at %s") % datetime.datetime.now(),
                'monospace', 'info')

        self.timer = Timer(prefs.log_interval, self.update)

    def update(self):
        self._logwatcher.update()
        unseen = self._logwatcher.get_unseen()
        # remove the date (like eximon)
        unseen = \
            map(lambda s: s[s.find(' ')+1:], unseen)

        # show the new data
        for line in unseen:
            # check for time signature
            if len(line) > 9 and line[2] == ':' and line[5] == ':':
                self.buffer.insert_with_tags_by_name(
                        self.buffer.get_end_iter(),
                        "\n" + line[:9],
                        'monospace', 'time')
            else: # no time signature, print everything and continue
                self.buffer.insert_with_tags_by_name(
                        self.buffer.get_end_iter(),
                        "\n" + line,
                        'monospace')
                continue
            # check for message id
            if len(line) > 25 and line[15] == '-' and line[22] == '-':
                self.buffer.insert_with_tags_by_name(
                        self.buffer.get_end_iter(), line[9:25],
                        'monospace', 'message_id')
                self.buffer.insert_with_tags_by_name(
                        self.buffer.get_end_iter(), line[25:],
                        'monospace', 'info')
            else: # no message id, print everything and continue
                self.buffer.insert_with_tags_by_name(
                        self.buffer.get_end_iter(), line[9:],
                        'monospace', 'info')

        if unseen: # if there was new data
            # discard old data if there's too much of it
            line_count = self.buffer.get_line_count()
            if line_count > self.MAX_LOG_LINES:
                start = self.buffer.get_start_iter()
                middle = self.buffer.get_iter_at_line_index(
                        int(line_count - self.MAX_LOG_LINES*0.8), 0)
                self.buffer.delete(start, middle)
            if self._track_log:
                self.scroll_to_mark(self.buffer.get_mark('end'), 0.0)

    def apply_prefs(self, prefs):
        self._track_log = prefs.track_log
        self.set_wrap_mode(prefs.wrap_log)
        self.timer.update_interval(prefs.log_interval)
        self._logwatcher.use_sudo = prefs.use_sudo
        self._logwatcher.use_ssh = prefs.use_ssh
        self._logwatcher.hostname = prefs.hostname
        if (self._logwatcher.log_dir != prefs.log_dir
           or self._logwatcher.mainlog_name != prefs.mainlog_name):
            self._logwatcher._valid = True
            self._logwatcher.open(prefs.log_dir, prefs.mainlog_name)
        self.update()


class ProcessWidget(gtk.TreeView):
    """A widget that displays a list of processes."""

    def __init__(self, statusbar, prefs):
        self._statusbar = statusbar
        self._old_processes = {}
        self.process_mgr = ProcessManager(self.do_update,
                prefs.bin_dir, prefs.use_sudo, prefs.use_ssh, prefs.hostname)

        self.model = gtk.ListStore(gobject.TYPE_INT,      # 0 pid
                                   gobject.TYPE_STRING)   # 1 status

        gtk.TreeView.__init__(self, self.model)
        self.connect('button-press-event', self.click)
        self.connect('popup-menu', self.popupMenu)

        renderer = gtk.CellRendererText()

        for index, title in enumerate(["PID", "Status"]):
            column = gtk.TreeViewColumn(title, renderer, text=index)
            column.set_reorderable(True)
            column.set_resizable(True)
            column.set_sort_column_id(index)
            self.append_column(column)

        self.get_column(0).clicked() # sort by pid
        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.set_headers_clickable(True)

        prefs.subscribe(self.apply_prefs)
        self.timer = Timer(prefs.process_interval, self.update)

    def update(self, new_status="Running exiwhat..."):
        """Schedule an immediate update of process status."""
        self._statusbar.pop(0)
        self._statusbar.push(0, new_status)
        self.process_mgr.schedule_update()

    def do_update(self, processes, info):
        """Update the process list.

        Called from a background thread.
        """
        gtk.threads_enter()
        try:
            old_processes = self._old_processes

            # remove outdated entries
            iter = self.model.get_iter_first()
            while iter is not None:
                next = self.model.iter_next(iter)
                pid = self.model.get_value(iter, 0)

                if (pid not in processes or 
                        old_processes[pid] != processes[pid]):
                    self.model.remove(iter)
                iter = next

            # add new and changed entries to list
            for pid, status in processes.iteritems():
                if pid not in old_processes or old_processes[pid] != status:
                    self.model.append((pid, status))

            self._old_processes = processes

            self._statusbar.pop(0)
            self._statusbar.push(0, info)
        finally:
            gtk.threads_leave()

    def click(self, widget, event):
        """Handle a click in the process widget."""
        if event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
            self.popupMenu(widget, event.button)
            return True     # handled
        else:
            return False    # not handled

    def popupMenu(self, widget, button=0):
        """Pop up the context menu."""
        menu = ProcessContextMenu(self.get_selection(), self)
        menu.show_all()
        menu.popup(None, None, None, button, gtk.get_current_event_time())

    def cleanup(self):
        """Clean up when the widget is destroyed."""
        self.process_mgr.stop()

    def apply_prefs(self, prefs):
        self.process_mgr.bin_dir = prefs.bin_dir
        self.process_mgr.use_sudo = prefs.use_sudo
        self.process_mgr.use_ssh = prefs.use_ssh
        self.process_mgr.hostname = prefs.hostname
        self.timer.set_paused(not prefs.show_process_list)
        self.timer.update_interval(prefs.process_interval)


class ProcessContextMenu(gtk.Menu):
    """Context menu for the process list."""

    def __init__(self, selection, process_widget):
        super(ProcessContextMenu, self).__init__()
        self._process_widget = process_widget

        pids = self.selectedProcesses(selection)

        self.add(gtk.TearoffMenuItem())

        menuitem = gtk.MenuItem(_("_Refresh"))
        menuitem.connect('activate', lambda menuitem: process_widget.update())
        self.add(menuitem)

        self.add(gtk.SeparatorMenuItem())

        submenu = gtk.Menu()
        menuitem = gtk.MenuItem(_("SIG_TERM"))
        menuitem.connect('activate', self._killProcesses, pids, signal.SIGTERM)
        submenu.add(menuitem)
        menuitem = gtk.MenuItem(_("SIG_KILL"))
        menuitem.connect('activate', self._killProcesses, pids, signal.SIGKILL)
        submenu.add(menuitem)

        menuitem = gtk.MenuItem(_("_Signal"))
        menuitem.set_submenu(submenu)
        self.add(menuitem)

    def selectedProcesses(self, selection):
        """Return selected processes."""
        pids = []

        def callback(model, path, iter):
            pid = model.get_value(iter, 0)
            pids.append(pid)
        selection.selected_foreach(callback)

        return pids

    def _killProcesses(self, menuitem, pids, signal):
        """Send a signal to selected processes."""
        killed = []
        permissions_ok = True
        for pid in pids:
            try:
                os.kill(pid, signal)
                killed.append(pid)
            except OSError, e:
                if e.errno == 1: # permission denied
                    permissions_ok = False
        if not permissions_ok:
            status = _("Permission problems!")
        elif not killed:
            status = _("Process has already terminated.")
        else:
            process_word = len(killed) > 1 and _("processes") or _("process")
            status = _("Signal %d sent to %s %s.") % \
                    (signal, process_word, suffix, ", ".join(map(str, killed)))
        self._process_widget.update(new_status=status)


class QueueWidget(gtk.TreeView):
    """A widget that displays the exim message queue."""

    def __init__(self, main_win, logwatcher, queue_mgr, prefs):
        self._main_win = main_win # needed for popups
        self._statusbar = main_win.statusbar
        self._old_queue = {}
        self.queue_mgr = queue_mgr
        self.queue_mgr.callback = self.do_update
        self.logwatcher = logwatcher

        self.model = gtk.ListStore(gobject.TYPE_STRING, # 0 color
                                   gobject.TYPE_STRING, # 1 message id
                                   gobject.TYPE_STRING, # 2 sender
                                   gobject.TYPE_STRING, # 3 size
                                   gobject.TYPE_STRING, # 4 time in queue
                                   gobject.TYPE_STRING) # 5 recipients

        # GTK's recent addition, 'fixed_height_mode' would be really useful
        # to speed things up, however, it is not yet supported by pyGTK

        renderer = gtk.CellRendererText()
        renderer.set_property('family', 'Monospace')
        id_column = gtk.TreeViewColumn(_("Message ID"), renderer, text=1)
        id_column.add_attribute(renderer, 'foreground', 0)

        gtk.TreeView.__init__(self, self.model)
        self.connect('button-press-event', self.click)
        self.connect('popup-menu', self.popupMenu)

        self.total_str = ""
        self.selected_str = ""
        self.get_selection().connect('changed', self.selectionChanged)

        renderer = gtk.CellRendererText()
        columns = ([id_column] +
                [gtk.TreeViewColumn(title, renderer, text=source)
                 for source, title in
                 [(2, _("Sender")), (3, _("Size")), (4, _("Time")),
                  (5, _("Recipients"))]])

        for index, column in enumerate(columns):
            column.set_reorderable(True)
            column.set_resizable(True)
            column.set_sort_column_id(index + 1) # not very neat, but it works
            self.append_column(column)

        self._setUpSorting()

        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.set_headers_clickable(True)
        self.set_rules_hint(True)

        self._initializing = True

        self.confirm_actions = prefs.confirm_actions
        self.report_success = prefs.report_success
        prefs.subscribe(self.apply_prefs)
        self.timer = Timer(prefs.queue_interval, self.update)

    def _setUpSorting(self):
        """Set up correct sorting by size and time."""

        def sort_func(treemodel, iter1, iter2, data):
            col_number, coef = data
            val1 = treemodel.get_value(iter1, col_number)
            val2 = treemodel.get_value(iter2, col_number)

            def eval_suffix(s, coef):
                if s is None or len(s) == 0:
                    return 0
                suffix = s[-1]
                if suffix in coef:
                    return float(s[:-1]) * coef[suffix]
                else:
                    return float(s)

            result = cmp(eval_suffix(val1, coef), eval_suffix(val2, coef))
            return result

        self.model.set_sort_func(3, sort_func,
                (3, {'K': 1024, 'M': 1048576}))
        self.model.set_sort_func(4, sort_func,
                (4, {'m': 1, 'h': 60, 'd': 24*60}))

    def update(self):
        """Schedule an immediate update of the queue list."""
        self.queue_mgr.schedule_update()

    def do_update(self, queue):
        """Update the process list.

        Called from a background thread.
        """
        # XXX this method is too long and needs to be split up

        gtk.threads_enter()
        if self._initializing:
            # the first update tends to be massive, so it is worth unbinding
            # the model from the view temporarily for performance reasons
            self.set_model(None)
            self.model.set_sort_column_id(0, gtk.SORT_ASCENDING)

        old_queue = self._old_queue

        # remove messages no longer in the queue from display
        iter = self.model.get_iter_first()
        while iter is not None:
            next = self.model.iter_next(iter)
            id = self.model.get_value(iter, 1)
            if id not in queue:
                self.model.remove(iter)
            elif queue[id] != old_queue[id]:
                msg = queue[id]
                self.model.set(iter,
                        0, msg.frozen and "#FF0000" or "#000000",
                        1, msg.id, 2, msg.sender, 3, msg.size,
                        4, msg.time, 5, " ".join(msg.recipients))
            iter = next
        gtk.threads_leave()

        # it is safe to do this now because the obsolete messages have been
        # removed and only new ones will be added
        self._old_queue = queue

        # find all messages which should be added to the model
        new_rows = []
        for id in queue:
            if id not in old_queue:
                msg = queue[id]
                row = (msg.frozen and "#FF0000" or "#000000",
                           msg.id, msg.sender, msg.size, msg.time,
                           " ".join(msg.recipients))
                new_rows.append(row)

        # reflect that the list is being updated in the statusbar;
        # only bother if there are many new messages
        worth_bothering = len(queue) > 100 and len(new_rows) > 10
        if self._initializing or worth_bothering:
            self.total_str = (_("Updating message list..."))
            gtk.threads_enter()
            self.updateStatusbar()
            gtk.threads_leave()

        if self._initializing:
            # the model is unbound so there is no need to call threads_enter()
            # and threads_leave() in every iteration; once is enough
            gtk.threads_enter()
            for row in new_rows:
                self.model.append(row)
            gtk.threads_leave()
        else:
            # the model is bound, so we need to do things the slow way
            # temporarily disabling sorting helps quite a bit
            if worth_bothering:
                gtk.threads_enter() # I HATE THESE!
                sort_mode = self.model.get_sort_column_id()
                self.model.set_sort_column_id(0, gtk.SORT_ASCENDING)
                gtk.threads_leave()
            for row in new_rows:
                gtk.threads_enter()
                self.model.append(row)
                gtk.threads_leave()
            if worth_bothering:
                gtk.threads_enter()
                self.model.set_sort_column_id(*sort_mode)
                gtk.threads_leave()

        # update the statusbar data
        msg_word = len(queue) > 1 and _("messages") or _("message")
        frozen = len(filter(lambda id: queue[id].frozen, queue))
        self.total_str = (_("%d %s in queue (%d frozen).") %
                                            (len(queue), msg_word, frozen))

        gtk.threads_enter()
        self.updateStatusbar()

        if self._initializing:
            self.set_model(self.model) # rebind the model
            self.model.set_sort_column_id(1, gtk.SORT_ASCENDING)
            self._initializing = False

        gtk.threads_leave()

    def click(self, widget, event):
        """Handle a click in the queue widget."""
        if event.type == gtk.gdk.BUTTON_PRESS and event.button == 3:
            self.popupMenu(widget, event.button)
            return True     # handled
        else:
            return False    # not handled

    def popupMenu(self, widget, button=0):
        """Pop up the context menu."""
        menu = QueueContextMenu(self.get_selection(), self._main_win, self)
        menu.show_all()
        menu.popup(None, None, None, button, gtk.get_current_event_time())

    def selectionChanged(self, selection):
        """Update statusbar on selection change."""
        messages = [0]
        def callback(model, path, iter):
            messages[0] += 1
        selection.selected_foreach(callback)
        messages = messages[0]
        # this could be done with a single line:
        # messages = selection.count_selected_rows()
        # but I think the current way is more compatible
        # with older versions of pygtk
        if messages:
            msg_word = messages > 1 and _("messages") or _("message")
            self.selected_str = _("%d %s selected.") % (messages, msg_word)
        else:
            self.selected_str = ""
        self.updateStatusbar()

    def updateStatusbar(self):
        """Update the statusbar."""
        # XXX this gets called from multiple threads, locking would be nice
        self._statusbar.pop(0)
        self._statusbar.push(0, self.total_str + ' ' + self.selected_str)

    def cleanup(self):
        """Clean up when the widget is destroyed."""
        self.queue_mgr.stop()

    def apply_prefs(self, prefs):
        self.queue_mgr.bin_dir = prefs.bin_dir
        self.queue_mgr.use_sudo = prefs.use_sudo
        self.queue_mgr.use_ssh = prefs.use_ssh
        self.queue_mgr.hostname = prefs.hostname
        self.confirm_actions = prefs.confirm_actions
        self.report_success = prefs.report_success
        self.timer.update_interval(prefs.queue_interval)
        self.update()

class QueueContextMenu(gtk.Menu):
    """Context menu for queued messages."""

    removeInfo = (_("removed"),
            _("The message(s) will be irreversibly deleted and "
              "no bounce messages will be sent."))
    giveupInfo = (_("discarded"),
            _("The message(s) will be deleted and a delivery error message "
              "will be sent to the sender."))
    markInfo = (_("marked as delivered"),
                _("The recipients who have not yet been processed will not "
                  "receive the message(s)."))


    def __init__(self, selection, main_win, queue_widget):
        # XXX should be split up into several methods
        gtk.Menu.__init__(self)
        self._queue_widget = queue_widget
        queue_mgr = queue_widget.queue_mgr
        self.logwatcher = queue_widget.logwatcher
        self._main_win = main_win
        self.confirm_actions = queue_widget.confirm_actions
        self.report_success = queue_widget.report_success

        queue = queue_widget._old_queue
        message_ids = self.selectedMessageIds(selection)
        messages = []
        for msg_id in message_ids[:]:
            if msg_id in queue:
                messages.append(queue[msg_id])
            else: # the queue view is inconsistent with internal data
                message_ids.remove(msg_id) # XXX ignore the message

        all_frozen = True
        all_unfrozen = True
        for msg in messages:
            if not msg.frozen:
                all_frozen = False
            else:
                all_unfrozen = False
        sel_none = len(message_ids) == 0
        sel_single = len(message_ids) == 1
        first_msg = sel_single and message_ids[0] or None

        def add_item(menu, label, sensitive, callback, *args):
            menuitem = gtk.MenuItem(label)
            menuitem.set_sensitive(sensitive)
            menuitem.connect('activate', callback, *args)
            menu.add(menuitem)

        self.add(gtk.TearoffMenuItem())
        add_item(self, _("_Refresh list"), True,
                lambda menuitem: queue_widget.update())
        self.add(gtk.SeparatorMenuItem())

        show_menu = gtk.Menu()
        add_item(show_menu, _("_Body"), sel_single, self._exim_popup,
                 queue_mgr.getMessageBody, first_msg, _("Body of"))
        add_item(show_menu, _("_Headers"), sel_single, self._exim_popup,
                 queue_mgr.getMessageHeaders, first_msg, _("Headers of"))
        add_item(show_menu, _("_Message log"), sel_single, self._exim_popup,
                 queue_mgr.getMessageLog, first_msg, _("Log of"))
        show_item = gtk.MenuItem(_("_Show"))
        show_item.set_submenu(show_menu)
        self.add(show_item)
        self.add(gtk.SeparatorMenuItem())

        grep_menu = gtk.Menu()
        params = (not sel_none, self._exigrep, message_ids)
        add_item(grep_menu, _("_ID"), not sel_none,
                 self._exigrep, messages, 'id')
        add_item(grep_menu, _("_Sender"), not sel_none,
                 self._exigrep, messages, 'sender')
        add_item(grep_menu, _("_Recipients"), not sel_none,
                 self._exigrep, messages, 'recipients')
        grep_item = gtk.MenuItem(_("_Exigrep"))
        grep_item.set_submenu(grep_menu)
        self.add(grep_item)
        self.add(gtk.SeparatorMenuItem())

        add_item(self, _("_Freeze"), not all_frozen, self._exim_action, None,
                 queue_mgr.freezeMessages, message_ids)
        add_item(self, _("_Thaw"), not all_unfrozen, self._exim_action, None,
                 queue_mgr.thawMessages, message_ids)
        self.add(gtk.SeparatorMenuItem())

        add_item(self, _("Re_move"), not sel_none, self._exim_action,
                 self.removeInfo, queue_mgr.removeMessages, message_ids)
        add_item(self, _("_Attempt to deliver"), not sel_none,
                 self._exim_action, None, queue_mgr.deliverMessages,
                 message_ids)
        add_item(self, _("_Give up"), not sel_none, self._exim_action,
                 self.giveupInfo, queue_mgr.giveUpMessages, message_ids)
        add_item(self, _("Mark as _delivered"), not sel_none,
                 self._exim_action,
                 self.markInfo, queue_mgr.markAllDelivered, message_ids)
        self.add(gtk.SeparatorMenuItem())

        add_item(self, _("_Change sender"), sel_single, self._exim_entry,
                 queue_mgr.editSender, first_msg,
                 _("Change the sender of "), _("Sender address:"))
        add_item(self, _("Add reci_pients"), sel_single, self._exim_entry,
                 queue_mgr.addRecipients, first_msg,
                 _("Add recipients to "), _("Enter the new recipients:"))

    def selectedMessageIds(self, selection):
        """Return ids of selected messages."""
        messages = []
        def callback(model, path, iter):
            messages.append(model[path[0]][1])
        selection.selected_foreach(callback)
        return messages

    def _exim_action(self, menuitem, msg_info, callable, message_ids):
        """Perform an action on message(s).

        Shows the user a dialog requesting to confirm the action. Calls
        `callable`, shows a dialog with the result.
        `callable` is expected to return a tuple: (action_successful, message).
        `msg_info` is a tuple of two strings describing the action.
        `message_ids` is a list of strings (message ids).
        """
        if self.confirm_actions and msg_info:
            num = len(message_ids) > 1 and (" " + str(len(message_ids))) or ""
            msg_word = len(message_ids) > 1 and _("messages") or _("message")
            dialog = AlertDialog(self._main_win,
                    _("The%s selected %s will be %s.")
                            % (num, msg_word, msg_info[0]), msg_info[1],
                            query=True)
            response = dialog.ask()
            if not response:
                return
        (success, status_msg) = callable(message_ids)
        if status_msg and (not success or self.report_success):
            if success:
                AlertDialog(self._main_win, _("Action successful."),
                        status_msg).ask()
            else:
                AlertDialog(self._main_win, _("There were problems."),
                        status_msg, error=True).ask()

        self._queue_widget.update()

    def _exim_popup(self, menuitem, callable, id, title_prefix):
        """Show a popup window with the string returned by callable."""
        (success, text) = callable(id)
        if success:
            popup = PopupWindow(title_prefix + id, text)
            popup.show_all()
        else:
            AlertDialog(self._main_win, _("An error occured."),
                    text, error=True).ask()

    def _exim_entry(self, menuitem, callable, id, title_prefix, label_text):
        """Show an entry dialog, input data ant pass it to `callable`.

        `id` is a string (the message id).
        `title_prefix` is the prefix for the entry window title.
        `label_text` is the text of the label in the dialog."""
        popup = EntryDialog(main_window=self._main_win,
                            title=(title_prefix + " " + id),
                            label_text=label_text)
        input = popup.get_input()
        if input:
            (success, status_msg) = callable(id, input)
            if not success:
                AlertDialog(self._main_win, _("An error occured."),
                        status_msg, error=True).ask()
            elif self.report_success:
                AlertDialog(self._main_win, _("Action successful."),
                        status_msg).ask()
            self._queue_widget.update()

    def _exigrep(self, menuitem, messages, field):
        """Run exigrep with data of selected messages.

        `messages` is a list of Message objects (not ids).
        `field` is a string indicating the field to run exigrep on.
        """
        if field == 'id':
            strings = [msg.id for msg in messages]
        elif field == 'sender':
            strings = [msg.sender for msg in messages]
        elif field == 'recipients':
            strings = []
            for msg in messages:
                strings += msg.recipients
        else:
            raise ValueError("Invalid field identifier.")

        pattern = '|'.join([re.escape(s) for s in strings])
        text = self.logwatcher.runExigrep(pattern, False, True)
        if text:
            PopupWindow("Exigrep: " + pattern, text.strip()).show_all()
        else:
            text = _()
            AlertDialog(self._main_win, "Empty output from exigrep.",
                  _("exigrep returned no data.")).ask()


class ExigrepDialog(EntryDialog):
    """An entry dialog that asks for information to pass to exigrep,
    invokes exigrep and shows the output in a popup window."""

    def __init__(self, main_window=None, text=""):
        EntryDialog.__init__(self, main_window,
                title=_("Run exigrep"), label_text=_("Search for:"))
        self._main_win = main_window
        self._statusbar = main_window.statusbar

        self.entry.set_text(text)
        self.regexp = gtk.CheckButton(_("Parse as a regular expression"))
        self.regexp.set_active(True)
        self.all_logs = gtk.CheckButton(_("Scan all logfiles"))
        self.all_logs.set_active(True)

        checkbuttons = gtk.VBox()
        checkbuttons.add(self.regexp)
        checkbuttons.add(self.all_logs)
        self.vbox.add(checkbuttons)

    def go(self, logwatcher):
        pattern = self.get_input()
        if pattern:
            text = logwatcher.runExigrep(pattern,
                    not self.regexp.get_active(), self.all_logs.get_active())
            if text:
                popup = PopupWindow("Exigrep: " + pattern, text.strip())
                popup.show_all()
            else:
                text = _("Empty output from exigrep.")
                AlertDialog(self._main_win, text,
                      _("exigrep returned no data. You may want to "
                        "refine your search terms or try a search on all "
                        "the log files.")).ask()


class EximstatsDialog(EntryDialog):
    """An entry dialog that asks for parameters and options to eximstats,
    invokes them and shows output in a popup window."""

    def __init__(self, main_window=None):
        EntryDialog.__init__(self, main_window,
                title=_("Run eximstats"),
                label_text=_("Arguments to eximstats:"))
        self._statusbar = main_window.statusbar
        self.all_logs = gtk.CheckButton(_("Scan all logfiles"))
        self.all_logs.set_active(True)
        self.vbox.add(self.all_logs)

    def go(self, logwatcher):
        self.show_all()
        response = self.run()
        args = self.entry.get_text()
        all_logs = self.all_logs.get_active()
        self.destroy()
        if response == gtk.RESPONSE_OK:
            text = logwatcher.runEximstats(args, all_logs)
            popup = PopupWindow("Eximstats", text.strip())
            popup.show_all()
