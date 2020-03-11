"""
AACircuit
2020-03-02 JvO
"""

import os
import sys
import cairo

from application.component_library import ComponentLibrary
from application.grid import Grid
from application.grid_canvas import GridCanvas

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk  # noqa: E402
# from gi.repository import GLib  # noqa: E402
from gi.repository import GdkPixbuf  # noqa: E402


class MainWindow(Gtk.Window):
    __gtype_name__ = "MainWindow"

    def __new__(cls):
        """
        This method creates and binds the builder window to the class.
        In order for this to work correctly, the class of the main
        window in the Glade UI file must be the same as the name of
        this class.
        """
        app_path = os.path.dirname(__file__)
        try:
            builder = Gtk.Builder()
            builder.add_from_file(os.path.join(app_path, "aacircuit.glade"))
        except IOError:
            print("Failed to load XML GUI file aacircuit.glade")
            sys.exit(1)

        new_object = builder.get_object('window1')
        new_object.finish_initializing(builder)

        return new_object

    def finish_initializing(self, builder):
        """
        Treat this as the __init__() method.
        Arguments pass in must be passed from __new__().
        """
        self.set_default_size(640, 480)

        # Add any other initialization here

        self.btn_cur = [
            builder.get_object("btn_cur1"),
            builder.get_object("btn_cur2"),
            builder.get_object("btn_cur3"),
            builder.get_object("btn_cur4")]

        self.btn_cur[0].set_name("btn_cur1")
        self.btn_cur[1].set_name("btn_cur2")
        self.btn_cur[2].set_name("btn_cur3")
        self.btn_cur[3].set_name("btn_cur4")

        self.btn_cur[0].set_active(True)

        self._init_cursors()

        # connect signals

        builder.connect_signals(self)
        self.connect('destroy', lambda w: Gtk.main_quit())

        for btn in self.btn_cur:
            btn.connect("toggled", self._on_toggled_cursor)

        btn_close = builder.get_object("imagemenuitem5")
        btn_close.connect("activate", self._on_close_clicked)

        # component libraries

        self.lib = ComponentLibrary()
        print("Number of component libraries loaded: {0}".format(self.lib.nr_libraries()))

        # the ASCII grid

        self.grid = Grid(75, 40)

        fixed = builder.get_object("viewport1")

        grid_canvas = GridCanvas()
        grid_canvas.grid = self.grid
        self._grid_canvas = grid_canvas

        fixed.add(grid_canvas)

    def _init_cursors(self):
        self._cursor = []
        for i in range(1, 4):
            self._cursor.append(GdkPixbuf.Pixbuf.new_from_file("buttons/c{0}.png".format(i)))

    def _on_toggled_cursor(self, button, data=None):

        if button.get_active():

            name = button.get_name()
            btn = int(name[-1])
            self.custom_cursor(btn)

            # disable the other cursor buttons
            for btn in self.btn_cur:
                if btn.get_name() != button.get_name():
                    # print("Button: %s" % btn.get_name())
                    btn.set_active(False)

    def _on_open_clicked(self, button):
        print("\"Open\" button was clicked")

    def _on_close_clicked(self, button):
        print("Closing application")
        Gtk.main_quit()

    def custom_cursor(self, btn):
        # https://askubuntu.com/questions/138336/how-to-change-the-cursor-to-hourglass-in-a-python-gtk3-application
        # cursor = Gdk.Cursor.new(Gdk.CursorType.WATCH)

        # https://developer.gnome.org/gdk3/stable/gdk3-Cursors.html#gdk-cursor-new-from-name
        if btn == 1:
            cursor = Gdk.Cursor.new(Gdk.CursorType.LEFT_PTR)
        elif btn == 2:
            cursor = Gdk.Cursor.new(Gdk.CursorType.CROSSHAIR)
        elif btn == 3:
            cursor = Gdk.Cursor.new(Gdk.CursorType.WATCH)
        elif btn == 4:
            cursor = Gdk.Cursor.new(Gdk.CursorType.CROSSHAIR)
        self.get_root_window().set_cursor(cursor)

    def custom_cursor_XXX(self, btn):
        # display = self.get_screen().get_display()
        # pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 100, 100)
        # cursor = Gdk.Cursor.new_from_pixbuf(display, pb, 100, 100)
        # pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 100, 100)
        # self.get_root_window().set_cursor(cursor)

        # https: // stackoverflow.com / questions / 55283386 / noisy - cairo - created - custom - cursor - in -gtk3
        display = self.get_screen().get_display()
        # pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 2 * radius, 2 * radius)
        pb = GdkPixbuf.Pixbuf.new_from_file("buttons/c{0}.bmp".format(btn))
        surface = Gdk.cairo_surface_create_from_pixbuf(pb, 0, None)

        # context = cairo.Context(surface)
        cursor = Gdk.Cursor.new_from_pixbuf(display, pb, 16, 16)
        self._grid_canvas.drawing_area.get_screen().get_root_window().set_cursor(cursor)

    def custom_cursor_YYY(self, radius):
        display = self.get_screen().get_display()
        pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 2 * radius, 2 * radius)
        surface = Gdk.cairo_surface_create_from_pixbuf(pb, 0, None)
        context = cairo.Context(surface)
        context.arc(radius, radius, radius, 0, 2 * np.pi)
        context.set_source_rgba(0, 0, 0, 1)
        context.stroke()
        pbdrawn = Gdk.pixbuf_get_from_surface(surface, 0, 0, surface.get_width(), surface.get_height())
        cursor = Gdk.Cursor.new_from_pixbuf(display, pbdrawn, radius, radius)
        self.darea.get_screen().get_root_window().set_cursor(cursor)
