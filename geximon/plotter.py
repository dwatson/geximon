"""Plotting of exim stats."""

import gtk
import gobject
import re

from gtkhelpers import Timer

KEEP_HISTORY = 2000
DELTA = 0.0000001

class Plotter(gtk.DrawingArea):
    """A widget that contains multiple color-coded plots."""

    config = [# label,   regexp,               color
               ('in',    ' <= ',               'yellow'),
               ('out',   ' => ',               'red'),
               ('local', ' => .+ R=local',     'blue'),
               ('smtp',  ' => .+ T=[^ ]*smtp', 'green'),
               ('queue', None,                 'white'),
             ]

    def __init__(self, logwatcher, queue_mgr, prefs):
        gtk.DrawingArea.__init__(self)

        self._logwatcher = logwatcher
        self._queue_mgr = queue_mgr

        self.set_size_request(-1, prefs.plot_area_height)
        self.visible = True
        self.interval = prefs.plotting_interval
        prefs.subscribe(self.apply_prefs)

        self.pangolayout = self.create_pango_layout("")
        self.gc = None # can't create as the window isn't realized yet
        colormap = self.get_colormap()
        self.background_color = colormap.alloc_color('black')
        self.guide_colors = [colormap.alloc_color('#AAAAAA'),
                             colormap.alloc_color('#555555'),
                             colormap.alloc_color('#222222')]

        self.plots = []
        for label, regex, color in self.config:
            compiled_regex = regex and re.compile(regex) or None
            mapped_color = colormap.alloc_color(color)
            history = []
            self.plots.append((label, compiled_regex, mapped_color, history))

        self.connect('expose-event', self._redraw)
        self.timer = Timer(self.interval, self.update)

    def _redraw(self, area, event):
        """Redraw the plots.
        
        Must not be invoked directly, because double-buffering won't work;
        queue_redraw() should be used instead.
        """
        geometry = self.window.get_geometry()
        width, height = geometry[2], geometry[3]
        if not self.gc:
            self.gc = self.window.new_gc()

        # clear drawing area
        self.gc.set_foreground(self.background_color)
        self.window.draw_rectangle(self.gc, True, 0, 0, width, height)

        start_x = 18
        point_count = width - start_x
        plot_height = height - 20
        label_offset = start_x + 10
        self._draw_guides(width, plot_height, start_x)
        for label, compiled_regex, mapped_color, history in self.plots:
            scale = self.get_scale(history)
            self.gc.set_foreground(mapped_color)
            if len(history) > 1:
                # transform data points to screen coordinates
                points = enumerate(history[-point_count:])
                coord_list = [(start_x + index, 
                               int(plot_height * (1 - value*scale)))
                               for index, value in points]
                self.window.draw_lines(self.gc, coord_list)
            # draw label
            if label_offset < width:
                suffix = ": %.1f" % (history and history[-1] or 0)
                if abs(scale - 0.1) > DELTA:
                    suffix = (" (%dx)" % (0.1/scale)) + suffix
                self.pangolayout.set_text(label + suffix)
                self.window.draw_layout(self.gc, label_offset, plot_height,
                                                            self.pangolayout)
                label_offset += len(label + suffix) * 9 # XXX text width
        return True
    
    def _draw_guides(self, width, plot_height, start_x):
        """Draw guide lines."""
        # draw main boundaries
        self.gc.set_foreground(self.guide_colors[0])
        self.window.draw_line(self.gc, start_x, 0, width, 0)
        self.window.draw_line(self.gc,
                start_x, plot_height, width, plot_height)
        # draw numbers
        # XXX hardcoding font sizes
        number_offset = 0
        self.pangolayout.set_text("10")
        self.window.draw_layout(self.gc, number_offset,
                -2, self.pangolayout)
        self.pangolayout.set_text("  5")
        self.window.draw_layout(self.gc, number_offset,
                plot_height / 2 - 8, self.pangolayout)
        self.pangolayout.set_text("  0")
        self.window.draw_layout(self.gc, number_offset,
                plot_height - 16, self.pangolayout)
        # draw a nice line indicating 5
        self.gc.set_foreground(self.guide_colors[1])
        self.window.draw_line(self.gc,
                start_x, plot_height / 2, width, plot_height / 2)
        # draw minor lines
        self.gc.set_foreground(self.guide_colors[2])
        for v in [1, 2, 3, 4, 6, 7, 8, 9]:
            y =  int(plot_height * (v / 10.0))
            self.window.draw_line(self.gc, start_x, y, width, y)

    def get_scale(self, list):
        """Calculate a scaling value for a list of floats.

        Returns a floating point value - a multiplier to normalize the data.
        """
        if len(list) < 2 or max(list) < 10:
            return 0.1
        largest = max(list)
        scale = 1.0
        while largest*scale > 1:
            scale /= 10
        return scale

    def update(self, *ignored_arguments):
        """Update plot data."""
        new_loglines = self._logwatcher.get_for_processing()
        for label, compiled_regex, mapped_color, history in self.plots:
            if label == 'queue':
                norm_count = float(self._queue_mgr.queue_length)
            else:
                count = self.count_matches(compiled_regex, new_loglines)
                norm_count = count * (1000.0 / self.interval) # normalize
            history.append(norm_count)
            if len(history) > KEEP_HISTORY:
                history.pop(0)
        self.queue_draw()

    def count_matches(self, regex, lines):
        count = 0
        for line in lines:
            if regex.search(line):
                count += 1
        return count

    def apply_prefs(self, prefs):
        self.set_size_request(-1, prefs.plot_area_height)
        self.interval = prefs.plotting_interval
        self.timer.update_interval(self.interval)
        if prefs.show_plotter != self.visible:
            self.set_visible(prefs.show_plotter)
        self.queue_draw()

    def set_visible(self, visible):
        self.visible = visible
        parent = self.get_parent()  # hide the frame as well
        if visible:
            parent.show_all()
        else:
            parent.hide()
