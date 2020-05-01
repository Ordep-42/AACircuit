"""
AACircuit.py
2020-03-02 JvO
"""

import re
import json
import xerox
import collections
from pubsub import pub

from application import _
from application import REMOVE, INSERT
from application import ERASER, COMPONENT, CHARACTER, TEXT, COL, ROW, DRAW_RECT, LINE, MAG_LINE, DIR_LINE
from application.pos import Pos
from application.grid import Grid
from application.preferences import Preferences
from application.main_window import MainWindow
from application.component_library import ComponentLibrary
from application.file import InputFileChooser, AsciiFileChooser, OutputFileChooser, PDFFileChooser, PrintOperation
from application.symbol import Eraser, Character, Text, Line, MagLine, DirLine, Rect, Row, Column

SelectedObjects = collections.namedtuple('SelectedObjects', ['startpos', 'symbol'])
Action = collections.namedtuple('Action', ['action', 'symbol'])


class Controller(object):

    def __init__(self):

        self.prefs = Preferences()

        self.gui = MainWindow()
        self.components = ComponentLibrary()

        self.init_stack()
        self.init_grid()

        all_components = [key for key in self.components.get_dict()]
        if self.components.nr_libraries() == 1:
            msg = _("One library loaded, total number of components: {0}").format(self.components.nr_components())
        else:
            msg = _("{0} libraries loaded, total number of components: {1}").format(self.components.nr_libraries(),
                                                                                    self.components.nr_components())
        pub.sendMessage('STATUS_MESSAGE', msg=msg)
        pub.sendMessage('ALL_COMPONENTS', list=all_components)

        # subscriptions

        pub.subscribe(self.on_character_changed, 'CHARACTER_CHANGED')
        pub.subscribe(self.on_component_changed, 'COMPONENT_CHANGED')

        pub.subscribe(self.on_rotate_symbol, 'ROTATE_SYMBOL')
        pub.subscribe(self.on_mirror_symbol, 'MIRROR_SYMBOL')

        pub.subscribe(self.on_paste_objects, 'PASTE_OBJECTS')
        pub.subscribe(self.on_paste_mag_line, 'PASTE_MAG_LINE')
        pub.subscribe(self.on_paste_dir_line, 'PASTE_DIR_LINE')
        pub.subscribe(self.on_paste_line, 'PASTE_LINE')
        pub.subscribe(self.on_paste_rect, 'PASTE_RECT')
        pub.subscribe(self.on_paste_text, 'PASTE_TEXT')
        pub.subscribe(self.on_paste_text, 'PASTE_TEXTBLOCK')
        pub.subscribe(self.on_undo, 'UNDO')
        pub.subscribe(self.on_redo, 'REDO')

        pub.subscribe(self.on_eraser_selected, 'ERASER')
        pub.subscribe(self.on_select_rect, 'SELECT_RECT')
        pub.subscribe(self.on_select_objects, 'SELECT_OBJECTS')

        # insert/remove rows or columns
        pub.subscribe(self.on_grid_col, 'GRID_COL')
        pub.subscribe(self.on_grid_row, 'GRID_ROW')

        # clipboard
        pub.subscribe(self.on_cut, 'CUT')
        pub.subscribe(self.on_copy, 'COPY')
        pub.subscribe(self.on_copy_grid, 'COPY_GRID')

        pub.subscribe(self.on_paste_grid, 'PASTE_GRID')
        pub.subscribe(self.on_load_and_paste_grid, 'LOAD_AND_PASTE_GRID')
        pub.subscribe(self.on_load_ascii_from_file, 'LOAD_ASCII_FROM_FILE')

        # file
        pub.subscribe(self.on_new, 'NEW_FILE')
        pub.subscribe(self.on_open, 'OPEN_FILE')
        pub.subscribe(self.on_save, 'SAVE_FILE')
        pub.subscribe(self.on_save_as, 'SAVE_AS_FILE')
        pub.subscribe(self.on_export_as_pdf, 'EXPORT_AS_PDF')

        # pub.subscribe(self.on_begin_print, 'BEGIN_PRINT')
        pub.subscribe(self.on_print_file, 'PRINT_FILE')
        pub.subscribe(self.on_end_print, 'END_PRINT')

        # open/save grid from/to file
        pub.subscribe(self.on_read_from_file, 'READ_FROM_FILE')
        pub.subscribe(self.on_write_to_file, 'WRITE_TO_FILE')

        # grid
        pub.subscribe(self.on_grid_size, 'GRID_SIZE')
        pub.subscribe(self.on_redraw_grid, 'REDRAW_GRID')

    def init_stack(self):
        # action stack with the last cut/pasted symbol(s)
        self.latest_action = []

        # redo stack that contains the last undone actions
        self.undone_action = []

        # all objects on the grid
        self.objects = []

        self.selected_objects = []

    def init_grid(self, cols=None, rows=None):

        if cols is None:
            self._cols = Preferences.values['DEFAULT_COLS']
        else:
            self._cols = cols

        if rows is None:
            self._rows = Preferences.values['DEFAULT_ROWS']
        else:
            self._rows = rows

        self.grid = Grid(self._cols, self._rows)
        pub.sendMessage('NEW_GRID', grid=self.grid)

    def show_all(self):
        self.gui.show_all()

    def revert_action(self, stack):

        def cut_symbol():
            self.remove_from_objects(symbol)
            symbol.remove(self.grid)

        def paste_symbol():
            self.objects.append(symbol)
            symbol.paste(self.grid)

        action = None
        symbol = None

        if len(stack) > 0:

            action, symbol = stack.pop()

            # revert action
            if action == REMOVE:
                paste_symbol()
                action = INSERT

            elif action == INSERT:
                cut_symbol()
                action = REMOVE

        return symbol, action

    def on_undo(self):

        if len(self.latest_action) > 0:
            symbol, action = self.revert_action(self.latest_action)
            if action:
                self.push_undone(symbol, action)

        if len(self.latest_action) < 1:
            # there are no more actions to undo
            pub.sendMessage('UNDO_CHANGED', undo=False)

    def on_redo(self):

        if len(self.undone_action) > 0:
            symbol, action = self.revert_action(self.undone_action)
            if action:
                self.push_latest_action(symbol, action)

        if len(self.undone_action) < 1:
            # there are no more actions to redo
            pub.sendMessage('REDO_CHANGED', redo=False)

    def push_latest_action(self, symbol, action=INSERT):
        """Add a cut or paste action to the undo stack."""

        act = Action(action=action, symbol=symbol)
        self.latest_action.append(act)

        pub.sendMessage('UNDO_CHANGED', undo=True)

    def push_undone(self, symbol, action):
        """Add an undone action to the redo stack."""

        act = Action(action=action, symbol=symbol)
        self.undone_action.append(act)

        pub.sendMessage('REDO_CHANGED', redo=True)

    def add_selected_object(self, symbol):
        obj = SelectedObjects(symbol.startpos, symbol)
        self.selected_objects.append(obj)

    # File menu

    def on_new(self):
        self.init_grid()
        self.init_stack()
        pub.sendMessage('NOTHING_SELECTED')

    def on_open(self):
        dialog = InputFileChooser()  # noqa: F841

    def on_save(self):
        if self.filename is not None:
            self.on_write_to_file(self.filename)

    def on_save_as(self):
        dialog = OutputFileChooser()  # noqa: F841

    def on_export_as_pdf(self):
        dialog = PDFFileChooser()  # noqa: F841

    def on_end_print(self):
        msg = _("Finished printing")
        pub.sendMessage('STATUS_MESSAGE', msg=msg)

    def on_print_file(self):
        dialog = PrintOperation()  # noqa: F841
        dialog.run()

    # Edit menu

    def remove_from_objects(self, symbol):
        for idx, sym in enumerate(self.objects):
            # the id's differ as instances are copied before being added to the selection list
            # if id(sym) == id(symbol):
            if sym.startpos == symbol.startpos and sym.id == symbol.id:
                del self.objects[idx]
                break

    def find_selected(self, rect):
        """Find all symbols that are located within the selection rectangle."""

        ul, br = rect

        selected = []
        for symbol in self.objects:

            # select symbols of which the upper-left corner is within the selection rectangle
            if symbol.startpos.in_rect(rect):
                copy = symbol.copy()
                selection = SelectedObjects(startpos=ul, symbol=copy)
                selected.append(selection)

        # TODO Only one of multiple objects sharing the same position will be selected
        if len(selected) > 0:
            selected.sort(key=lambda x: x.startpos)
            selected_unique = []
            positions = set()
            for sel in selected:
                if sel.symbol.startpos in positions:
                    # print("Duplicates")
                    msg = _("More than one item at position: %s !" % sel.symbol.startpos)
                    pub.sendMessage('STATUS_MESSAGE', msg=msg)
                else:
                    positions.add(sel.symbol.startpos)
                    selected_unique.append(sel)
            selected = selected_unique

        self.selected_objects = selected

    def on_cut(self, rect):

        self.find_selected(rect)

        action = []
        for obj in self.selected_objects:

            act = Action(action=REMOVE, symbol=obj.symbol)
            action.append(act)

            obj.symbol.remove(self.grid)
            self.remove_from_objects(obj.symbol)

        self.latest_action += action

        pub.sendMessage('UNDO_CHANGED', undo=True)
        pub.sendMessage('OBJECTS_SELECTED', objects=self.selected_objects)

    def on_copy(self, rect):
        """Select all symbols that are located within the selection rectangle."""
        self.find_selected(rect)
        pub.sendMessage('OBJECTS_SELECTED', objects=self.selected_objects)

    # grid manipulation

    def on_grid_size(self, cols, rows):
        self._rows = rows
        self._cols = cols
        self.grid.resize(cols, rows)
        pub.sendMessage('GRID_SIZE_CHANGED')

    def on_redraw_grid(self):
        rows = self._rows
        cols = self._cols
        self.init_grid(cols, rows)
        for symbol in self.objects:
            symbol.paste(self.grid)

    def on_grid_col(self, col, action):

        symbol = Column(col, action)
        self.objects.append(symbol)
        symbol.paste(self.grid)

        self.push_latest_action(symbol, action)

    def on_grid_row(self, row, action):

        symbol = Row(row, action)
        self.objects.append(symbol)
        symbol.paste(self.grid)

        self.push_latest_action(symbol, action)

    # character/component symbol

    def on_character_changed(self, char):
        symbol = Character(char)
        self.selected_objects = []
        self.add_selected_object(symbol)
        pub.sendMessage('CHARACTER_SELECTED', char=symbol)

    def on_component_changed(self, label):
        symbol = self.components.get_symbol(label)
        self.selected_objects = []
        self.add_selected_object(symbol)
        pub.sendMessage('SYMBOL_SELECTED', symbol=symbol)

    def on_rotate_symbol(self):
        for obj in self.selected_objects:
            obj.symbol.rotate()

    def on_mirror_symbol(self):
        for obj in self.selected_objects:
            obj.symbol.mirrored = 1 - obj.symbol.mirrored  # toggle 0/1

    def on_paste_text(self, symbol):

        self.selected_objects = []
        self.add_selected_object(symbol)

        self.objects.append(symbol)
        symbol.paste(self.grid)

        self.push_latest_action(symbol)

        pub.sendMessage('UNDO_CHANGED', undo=True)

    def on_paste_objects(self, pos):
        """
        Paste selection.
        :param pos: the target position in grid (col, row) coordinates.
        """

        action = []

        for obj in self.selected_objects:

            offset = pos - obj.startpos

            # TODO make the position translation a Symbol method?
            symbol = obj.symbol.copy()
            symbol.startpos += offset
            symbol.endpos += offset

            act = Action(action=INSERT, symbol=symbol)
            action.append(act)

            self.objects.append(symbol)

            symbol.paste(self.grid)

        self.latest_action += action

        pub.sendMessage('NOTHING_SELECTED')
        pub.sendMessage('UNDO_CHANGED', undo=True)

    # lines

    def on_paste_line(self, startpos, endpos, type):
        symbol = Line(startpos, endpos, type)

        self.selected_objects = []
        self.add_selected_object(symbol)

        self.objects.append(symbol)
        symbol.paste(self.grid)
        self.push_latest_action(symbol)

    def on_paste_dir_line(self, startpos, endpos):
        symbol = DirLine(startpos, endpos)

        self.selected_objects = []
        self.add_selected_object(symbol)

        self.objects.append(symbol)
        symbol.paste(self.grid)
        self.push_latest_action(symbol)

    def on_paste_mag_line(self, startpos, endpos):
        symbol = MagLine(startpos, endpos, self.grid.cell)

        self.selected_objects = []
        self.add_selected_object(symbol)

        self.objects.append(symbol)
        symbol.paste(self.grid)
        self.push_latest_action(symbol)

    def on_paste_rect(self, startpos, endpos):
        symbol = Rect(startpos, endpos)

        self.selected_objects = []
        self.add_selected_object(symbol)

        self.objects.append(symbol)
        symbol.paste(self.grid)
        self.push_latest_action(symbol)

    # clipboard

    def on_copy_grid(self):
        self.grid.copy_to_clipboard()

    def on_paste_grid(self):
        """
        Copy the content of the clipboard to the grid.
        ASCII lines, terminated by CR, are interpreted as rows.
        """
        selected = []
        pos = Pos(0, 0)
        relative_pos = Pos(0, 0)

        content = xerox.paste().splitlines()

        for line in content:
            symbol = Text(relative_pos, line)
            selection = SelectedObjects(startpos=pos, symbol=symbol)
            selected.append(selection)
            relative_pos += Pos(0, 1)

        self.selected_objects = selected

        pub.sendMessage('OBJECTS_SELECTED', objects=self.selected_objects)

    def on_load_and_paste_grid(self):
        self.selected_objects = []
        dialog = AsciiFileChooser()  # noqa: F841

    def on_load_ascii_from_file(self, filename):

        try:
            file = open(filename, 'r')
            str = file.readlines()

            startpos = Pos(0, 0)
            pos = Pos(0, 0)
            for line in str:
                # create a TEXT instance for each line
                # fill selected_objects...
                symbol = Text(pos, line)
                selection = SelectedObjects(startpos=startpos, symbol=symbol)

                pos += Pos(0, 1)
                self.selected_objects.append(selection)

            file.close()

            pub.sendMessage('OBJECTS_SELECTED', objects=self.selected_objects)
            return True

        except (IOError, UnicodeDecodeError):
            print(_("Unable to open file for reading: %s" % filename))
            return False

    # other

    def on_eraser_selected(self, size):
        """Select eraser of the given size."""
        symbol = Eraser(size)

        self.selected_objects = []
        self.add_selected_object(symbol)

        pub.sendMessage('SYMBOL_SELECTED', symbol=symbol)

    def on_select_rect(self):
        """Select multiple objects."""
        pub.sendMessage('NOTHING_SELECTED')
        pub.sendMessage('SELECTING_RECT', objects=self.objects)

        msg = _("Selecting rectangle...")
        pub.sendMessage('STATUS_MESSAGE', msg=msg)

    def on_select_objects(self):
        """Select individual objects."""
        pub.sendMessage('NOTHING_SELECTED')
        pub.sendMessage('SELECTING_OBJECTS', objects=self.objects)

    # file open/save

    # TODO naar eigen file of class zetten

    def on_write_to_file(self, filename):

        try:
            fout = open(filename, 'w')

            str = ""
            for symbol in self.objects:
                str += symbol.memo() + "\n"
            fout.write(str)

            fout.close()

            self.filename = filename

            msg = _("Schema has been saved in: %s" % self.filename)
            pub.sendMessage('STATUS_MESSAGE', msg=msg)

            return True

        except IOError:
            msg = _("Unable to open file for writing: %s" % filename)
            pub.sendMessage('STATUS_MESSAGE', msg=msg)
            return False

    def on_read_from_file(self, filename):

        self.filename = filename

        try:
            file = open(filename, 'r')
            str = file.readlines()

            # start with a fresh grid
            self.init_stack()

            self.grid = Grid(72, 36)
            pub.sendMessage('NEW_GRID', grid=self.grid)

            memo = []
            for line in str:
                memo.append(line)

            file.close()

            skipped = self.play_memo(memo)

            # empty the undo stack (from the played memo actions)
            self.latest_action = []
            pub.sendMessage('UNDO_CHANGED', undo=False)

            if skipped > 0:
                msg = _("{0} lines skipped in {1}".format(skipped, filename))
            else:
                msg = "%s" % filename

            pub.sendMessage('STATUS_MESSAGE', msg=msg)
            pub.sendMessage('FILE_OPENED')
            pub.sendMessage('NOTHING_SELECTED')

            return True

        except (IOError, UnicodeDecodeError):
            msg = _("Unable to open file for reading: %s" % filename)
            pub.sendMessage('STATUS_MESSAGE', msg=msg)
            return False

    def play_memo(self, memo):

        skipped = 0

        for item in memo:

            m1 = re.search('(^eras|^comp|^char|^rect|^line|^magl|^dirl):(\d+),(\d+),(\d+),?(\d*),?(\d*),?(\d*)', item)  # noqa W605
            m2 = re.search('(^d|^i)(row|col):(\d+)', item)  # noqa W605
            m3 = re.search('(^text):(\d+),(\d+),(\d+),(.*)', item)  # noqa W605

            if m1 is not None:
                skipped += self.play_m1(m1)
            elif m2 is not None:
                skipped += self.play_m2(m2)
            elif m3 is not None:
                skipped += self.play_m3(m3)
            else:
                skipped += 1

        return skipped

    def play_m1(self, m):

        skip = 0
        type = m.group(1)

        if type == ERASER:

            w = int(m.group(2))
            h = int(m.group(3))
            size = (w, h)

            x, y = m.group(4, 5)
            pos = Pos(x, y)

            symbol = Eraser(size)

            self.selected_objects = []
            self.add_selected_object(symbol)

            self.on_paste_objects(pos)

        elif type == COMPONENT:

            id = m.group(2)

            orientation = int(m.group(3))
            mirrored = int(m.group(4))

            x, y = m.group(5, 6)
            pos = Pos(x, y)

            symbol = self.components.get_symbol_byid(id)
            symbol.ori = orientation
            symbol.mirrored = mirrored

            self.selected_objects = []
            self.add_selected_object(symbol)

            self.on_paste_objects(pos)

        elif type == CHARACTER:

            ascii = m.group(2)
            char = chr(int(ascii))

            x, y = m.group(3, 4)
            pos = Pos(x, y)

            symbol = Character(char)

            self.selected_objects = []
            self.add_selected_object(symbol)

            self.on_paste_objects(pos)

        elif type == LINE:

            terminal = int(m.group(2))

            x, y = m.group(3, 4)
            startpos = Pos(x, y)

            x, y = m.group(5, 6)
            endpos = Pos(x, y)

            self.on_paste_line(startpos, endpos, terminal)

        elif type == DIR_LINE:

            x, y = m.group(2, 3)
            startpos = Pos(x, y)

            x, y = m.group(4, 5)
            endpos = Pos(x, y)

            self.on_paste_dir_line(startpos, endpos)

        elif type == MAG_LINE:

            x, y = m.group(2, 3)
            startpos = Pos(x, y)

            x, y = m.group(4, 5)
            endpos = Pos(x, y)

            self.on_paste_mag_line(startpos, endpos)

        elif type == DRAW_RECT:

            x, y = m.group(2, 3)
            startpos = Pos(x, y)

            x, y = m.group(4, 5)
            endpos = Pos(x, y)

            self.on_paste_rect(startpos, endpos)

        else:
            skip = 1

        return skip

    def play_m2(self, m):

        skip = 0
        type = m.group(1)

        if type == 'i':
            action = INSERT
        else:
            action = REMOVE

        what = m.group(2)
        nr = int(m.group(3))

        if what == COL:
            self.on_grid_col(nr, action)

        elif what == ROW:
            self.on_grid_row(nr, action)

        else:
            skip = 1

        return skip

    def play_m3(self, m):

        skip = 0
        type = m.group(1)

        if type == TEXT:

            orientation = int(m.group(2))

            x, y = m.group(3, 4)
            pos = Pos(x, y)

            str = m.group(5)
            text = json.loads(str)

            symbol = Text(pos, text, orientation)

            self.selected_objects = []
            self.add_selected_object(symbol)

            self.on_paste_objects(pos)

        else:
            skip = 1

        return skip
