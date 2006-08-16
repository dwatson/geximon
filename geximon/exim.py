"""Interfacing with exim processes."""

import os, fcntl, select
import threading

__metaclass__ = type


def get_output(path='', filename='', args='', use_sudo=False, use_ssh=False, hostname=''):
    """Run a command and return its output."""
    stdouterr = get_pipe(path, filename, args, use_sudo, use_ssh, hostname)
    try:
        return stdouterr.read().strip()
    finally:
        stdouterr.close()

def get_pipe(path='', filename='', args='', use_sudo=False, use_ssh=False, hostname=''):
    """Run a command and return its handle."""
    cmd = (use_ssh and 'ssh %s '%hostname or '') + \
          (use_sudo and 'sudo ' or '') + \
          os.path.join(path, filename)
    if args:
        cmd += ' ' + args
    stdin, stdouterr = os.popen4(cmd)
    stdin.close()
    return stdouterr

class LogWatcher:
    """Watch exim logs."""

    def __init__(self, log_dir, mainlog_name, bin_dir, sudo, ssh, hostname, line_limit=500):
        self.line_limit = line_limit
        self.for_processing = []
        self._valid = True
        self.bin_dir = bin_dir
        self.use_sudo = sudo
        self.use_ssh = ssh
        self.hostname = hostname
        self.open(log_dir, mainlog_name)

    def open(self, log_dir, mainlog_name):
        self.log_dir = log_dir
        self.mainlog_name = mainlog_name
        mainlog_path = os.path.join(log_dir, mainlog_name)
        try:
    #        self.mainlog = open(mainlog_path)
    #        self.mainlog_inode = os.fstat(self.mainlog.fileno()).st_ino
    #        self._valid = True
            self.mainlog = get_pipe('/usr/bin','tail','-f %s'%mainlog_path,self.use_sudo, self.use_ssh, self.hostname)
            self.mainlog_fd = self.mainlog.fileno()
            fl = fcntl.fcntl(self.mainlog_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.mainlog_fd, fcntl.F_SETFL, fl|os.O_NONBLOCK)
            self._valid = True
        except IOError:
            if self._valid:
                # XXX should show a popup
                self.unseen = \
                    [_("Error: could not open the exim log file at `%s`!")
                                                              % mainlog_path]
                self._valid = False
            self.mainlog = None
        else:
    #        self.unseen = self.mainlog.readlines()[-self.line_limit:]
    #        self.unseen = [s[:-1] for s in self.unseen]
            self.unseen = []

    def update(self):
        """Read the log file for new entries."""
        mainlog_path = os.path.join(self.log_dir, self.mainlog_name)
        if self.mainlog:
            new_entries = []
            if (select.select([self.mainlog_fd],[],[],0))[0]:
                buffer = os.read(self.mainlog_fd, 2000)
                for line in buffer.split("\n"):
                    if line:
                        new_entries.append(line)
        else:
            new_entries = []
            self.open(self.log_dir, self.mainlog_name)
            return

        self.unseen += new_entries
        self.for_processing += new_entries

    def get_unseen(self):
        """Get unseen entries."""
        unseen = self.unseen
        self.unseen = []
        return unseen

    def get_for_processing(self):
        """Get list of lines that have not been processed yet."""
        for_processing = self.for_processing
        self.for_processing = []
        return for_processing

    def runExigrep(self, pattern, literal, all_logs):
        """Run exigrep with the provided pattern.

        `pattern` is a Perl regular expression, or a plain string - if
        `literal` is True. `all_logs` indicates if all logfiles (rather
        than just the latest one) should be scanned.
        """
        filename = os.path.join(self.log_dir, all_logs and '*'
                                              or self.mainlog_name)
        pattern = "'" + pattern + "'"
        return get_output(self.bin_dir, 'exigrep',
                (literal and '-l' or '') + pattern + ' ' + filename, self.use_sudo, self.use_ssh, self.hostname)

    def runEximstats(self, args, all_logs):
        """Run eximstats.

        `args` is a string containing the arguments to pass to eximstats,
        all_logs indicates if all logfiles should be scanned.
        """
        filename = os.path.join(self.log_dir, all_logs and '*'
                                              or self.mainlog_name)
        return get_output(self.bin_dir, 'eximstats', args + ' ' + filename, self.use_sudo, self.use_ssh, self.hostname)

    def getRejectlog(self):
        """Get the contents of the rejectlog."""
        # XXX this heuristic is unreliable and should be refactored
        filename = os.path.join(self.log_dir, 'rejectlog')
        if not os.path.exists(filename):
            filename = os.path.join(self.log_dir, 'reject.log')
        try:
            f = open(filename)
            text = f.read()
        except IOError:
            text = '' # XXX should indicate an error
        return text


class BackgroundJob:
    """On-demand background job manager.

    BackgroundJob starts a new background thread that goes to sleep.  When it
    is woken up (by calling schedule_update), it performs some background
    processing (do_update) and goes to sleep again.  Any calls to
    schedule_update while the background processing is active are ignored.

    The background thread can be stopped by calling stop.

    Subclasses must override do_update.
    """

    def __init__(self):
        self._quit = False
        self._synch = threading.Event()
        self._thread = threading.Thread(target=self.bg_processing)
        self._thread.setDaemon(True)
        self._thread.start()

    def bg_processing(self):
        """Perform background processing on demand."""
        while not self._quit:
            self._synch.wait()
            if self._quit:
                break
            self.do_update()
            self._synch.clear()

    def schedule_update(self):
        """Wake up the background thread."""
        self._synch.set()

    def stop(self, timeout=1.0):
        """Stop background processing."""
        self._quit = True
        self._synch.set()
        self._thread.join(timeout)

    def do_update(self):
        """Override this method to perform background jobs.

        It is called in a background thread.
        """
        raise NotImplementedError("You need to override do_update in %s"
                                  % self.__class__.__name__)


class QueueManager(BackgroundJob):
    """Exim queue manager.

    Queue manager calls exim and parses its output in a background thread to
    get the status of the exim queue.  Once the status is available, the queue
    manager calls the registered callback.
    """

    def __init__(self, callback, bin_dir, exim_binary, sudo, ssh, hostname):
        """Initialize and start the background thread.

        callback is a callable that takes one argument -- a mapping from
        message IDs to message objects.  It will be called from the background
        thread.

        bin_dir is the path to exim.
        use_sudo indicates if sudo is to be used.
        """
        BackgroundJob.__init__(self)
        self.callback = callback
        self.bin_dir = bin_dir
        self.exim_binary = exim_binary
        self.use_sudo = sudo
        self.use_ssh = ssh
        self.hostname = hostname
        self.queue_length = 0

    def do_update(self):
        """Get the current exim queue in a separate thread."""
        data = self.getEximOutput(['-bpr'])

        if (data.find('No such file or directory') != -1
                or data.find(' not found') != -1
                or data.find('exim: permission denied') != -1):
            # complain in case of problems
            m = Message()
            m.frozen, m.time, m.size, m.sender = True, "", "", "",
            # XXX should show a popup
            m.id, m.recipients = 'error', \
                [_("Error invoking `exim -bpr`:\n") + data]
            self.messages = {'error': m}
            self.callback(self.messages)
            return

        data = data.splitlines()
        messages = {}
        recipient_list = False
        message = None
        for line in data:
            if not recipient_list:
                try:
                    message = Message(status_line=line)
                except ValueError:
                    pass # probably an odd status line, ignore it
                else:
                    messages[message.id] = message
                recipient_list = True
            elif line:
                message.add_recipient(line)
            else:
                recipient_list = False
        self.queue_length = len(messages)
        self.callback(messages)

    def getEximOutput(self, args):
        """Invoke exim with arguments, return command output.

        args is a list of strings (the parameters to be passed).
        """
        return get_output(self.bin_dir, self.exim_binary,
                " ".join(args), self.use_sudo, self.use_ssh, self.hostname)

    def checkOutput(self, output, expected, msg_count, action_name):
        """Check if a string has `expected` as a substring on each line.

        Returns a tuple: (no_errors, report_string).
        """
        lines = output.splitlines()
        errors = filter(lambda s: s.find(expected) == -1, lines)
        if not errors:
            words = msg_count > 1 and 'messages have' or 'message has'
            success_report = _("%d %s been %s.") \
                    % (msg_count, words, action_name)
            return (True, success_report)
        else:
            return (False, "\n".join(errors))

    # -- general actions --

    def runQueue(self):
        """Run the queue now."""
        # XXX a little dirty, but will do for now
	cmd = ''
	if self.use_ssh:
		cmd = cmd + 'ssh %s ' % self.hostname
	if self.use_sudo:
		cmd = cmd + 'sudo '
	cmd = cmd + os.path.join(self.bin_dir, self.exim_binary) + ' -q &'
	os.system(cmd)
        return _("Spawning a queue runner in the background.")

    def getConfiguration(self):
        """Get all exim configuration options."""
        return self.getEximOutput(['-bP'])

    # -- message actions --
    # methods must return a tuple: (action_successful, message)

    def getMessageBody(self, id):
        """Get the body of the message with the given ID."""
        return (True, self.getEximOutput(['-Mvb', id]))

    def getMessageHeaders(self, id):
        """Get the headers of the message with the given ID."""
        return (True, self.getEximOutput(['-Mvh', id]))

    def getMessageLog(self, id):
        """Get the log of the message with the given ID."""
        return (True, self.getEximOutput(['-Mvl', id]))

    def removeMessages(self, ids):
        """Remove messages with given IDs."""
        output = self.getEximOutput(['-Mrm'] + ids)
        return self.checkOutput(output,
                "has been removed", len(ids), _("removed"))

    def freezeMessages(self, ids):
        """Freeze messages with given IDs."""
        output = self.getEximOutput(['-Mf'] + ids)
        return self.checkOutput(output,
                "is now frozen", len(ids), _("frozen"))

    def thawMessages(self, ids):
        """Unfreeze messages with given IDs."""
        output = self.getEximOutput(['-Mt'] + ids)
        return self.checkOutput(output,
                "is no longer frozen", len(ids), _("thawed"))

    def deliverMessages(self, ids):
        """Force the delivery of messages with given IDs."""
        return (True, self.getEximOutput(['-M'] + ids))

    def giveUpMessages(self, ids):
        """Give up trying to deliver messages with given IDs."""
        return (True, self.getEximOutput(['-Mg'] + ids))

    def addRecipients(self, id, recipients):
        """Add more recipients to a message with a given ID."""
        output = self.getEximOutput(['-Mar', id] + recipients.split())
        return self.checkOutput(output,
                "has been modified", 1, _("modified"))

    def editSender(self, id, sender):
        """Change the sender of a message with a given ID."""
        output = self.getEximOutput(['-Mes', id, sender])
        return self.checkOutput(output,
                "has been modified", 1, _("modified"))

    def markAllDelivered(self, ids):
        """Mark all recipients of messages with given IDs as delivered."""
        output = self.getEximOutput(['-Mmad'] + ids)
        return self.checkOutput(output,
                "has been modified", len(ids), _("marked as delivered"))


class Message:
    """A queued message.

    >>> line = '22h  1.2K 1AttSk-0002qB-00 <> *** frozen ***'
    >>> m = Message(line)
    >>> m.id, m.frozen, m.time, m.sender, m.size, m.recipients
    ('1AttSk-0002qB-00', True, '22h', '<>', '1.2K', [])
    >>> m.add_recipient(' foobar\\n')
    >>> m.recipients
    ['foobar']
    """

    def __init__(self, status_line=None):
        """Extract information from a message status line returned by exim."""
        if not status_line is None:
            parts = status_line.split()
            if len(parts) < 4:
                raise ValueError(_("Invalid status line: ") + status_line)
            self.id = parts[2]
            self.frozen = "frozen" in parts
            self.time = parts[0]
            self.size = parts[1]
            self.sender = parts[3]
            self.recipients = []

    def add_recipient(self, line):
        """Add a recipient to the message."""
        self.recipients.append(line.strip())

    def __eq__(self, other):
        return (self.id == other.id and self.frozen == other.frozen and
                self.time == other.time and self.size == other.size and
                self.sender == other.sender and
                self.recipients == other.recipients)

    def __ne__(self, other):
        return not self.__eq__(other)


class ProcessManager(BackgroundJob):
    """Exim process manager.

    Process manager calls exiwhat(8) and parses its output in a background
    thread to get the status of exim processes.  Once the status is available,
    the process manager calls the registered callback.
    """

    def __init__(self, callback, bin_dir, use_sudo, use_ssh, hostname):
        """Start the background thread.

        callback is a callable that takes one argument -- a mapping from
        process IDs to status messages.  It will be called from the background
        thread.

        bin_dir is the path to exim binaries.
        use_sudo indicates if sudo is to be used.
        """
        BackgroundJob.__init__(self)
        self.callback = callback
        self.bin_dir = bin_dir
        self.use_sudo = use_sudo
        self.use_ssh = use_ssh
        self.hostname = hostname

    def do_update(self):
        """Collect data from exiwhat in a separate thread."""
        data = get_output(self.bin_dir, 'exiwhat', use_sudo=self.use_sudo, use_ssh=self.use_ssh, hostname=self.hostname)

        processes = {}
        if (data.find('Permission denied') != -1 or
            data.find('Operation not permitted') != -1):
            # XXX need to be more verbose
            status = _("Permission problems!")
        elif data.find('No exim process data') != -1:
            status = _("No exim processes are currently running.")
        elif data == '':
            status = _("No output from exiwhat!")
        else:
            status = ""
            for line in data.splitlines():
                try:
                    id, info = line.split(None, 1)
                    id = int(id)
                    processes[id] = info.strip()
                except ValueError:
                    # probably trying to parse an error message
                    status = _("Error processing exiwhat output line: ") + line
            if not status:
                process_word = (len(processes) > 1 and _("processes")
                                                    or _("process"))
                status = _("%d exim %s.") % (len(processes), process_word)

        self.callback(processes, status)
