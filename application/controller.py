"""
AACircuit.py
2020-03-02 JvO
"""

import re
import json
import collections
from pubsub import pub

from application import _
from application import REMOVE, INSERT
from application import COMPONENT, CHARACTER, TEXT, COL, ROW, DRAW_RECT, LINE, MAG_LINE
from application.grid import Grid
from application.pos import Pos
from application.symbol import Symbol, Character, Text, Line, MagLine, Rect, Row, Column
from application.main_window import MainWindow
from application.component_library import ComponentLibrary
from application.file import FileChooserWindow


SelectedObjects = collections.namedtuple('selection', ['startpos', 'symbol', 'view'])
Action = collections.namedtuple('action', ['action', 'symbol'])


class Controller(object):

    def __init__(self):

        # setup MVC

        self.grid = Grid(72, 36)  # the ASCII grid

        self.gui = MainWindow()

        self.components = ComponentLibrary()
        self.symbol = Symbol()

        # last cut/pasted symbol(s)
        self.last_action = []

        # all objects on the grid
        self.objects = []

        self.selected_objects = []

        all_components = [key for key in self.components.get_dict()]
        if self.components.nr_libraries() == 1:
            print(_("One library loaded, total number of components: {0}").format(self.components.nr_components()))
        else:
            print(_("{0} libraries loaded, total number of components: {1}").format(self.components.nr_libraries(),
                                                                                    self.components.nr_components()))
        # messages

        # all_components.sort()
        pub.sendMessage('ALL_COMPONENTS', list=all_components)
        pub.sendMessage('GRID', grid=self.grid)

        # subscriptions

        pub.subscribe(self.on_character_changed, 'CHARACTER_CHANGED')
        pub.subscribe(self.on_component_changed, 'COMPONENT_CHANGED')

        pub.subscribe(self.on_rotate_symbol, 'ROTATE_SYMBOL')
        pub.subscribe(self.on_mirror_symbol, 'MIRROR_SYMBOL')

        pub.subscribe(self.on_paste_character, 'PASTE_CHARACTER')
        pub.subscribe(self.on_paste_symbol, 'PASTE_SYMBOL')
        pub.subscribe(self.on_paste_objects, 'PASTE_OBJECTS')
        pub.subscribe(self.on_paste_mag_line, 'PASTE_MAG_LINE')
        pub.subscribe(self.on_paste_line, 'PASTE_LINE')
        pub.subscribe(self.on_paste_rect, 'PASTE_RECT')
        pub.subscribe(self.on_paste_text, 'PASTE_TEXT')
        pub.subscribe(self.on_paste_text, 'PASTE_TEXTBLOCK')
        pub.subscribe(self.on_undo, 'UNDO')

        pub.subscribe(self.on_select_rect, 'SELECT_RECT')
        pub.subscribe(self.on_select_objects, 'SELECT_OBJECTS')

        # insert/remove rows or columns
        pub.subscribe(self.on_grid_col, 'GRID_COL')
        pub.subscribe(self.on_grid_row, 'GRID_ROW')

        # clipboard
        pub.subscribe(self.on_copy_to_clipboard, 'COPY_TO_CLIPBOARD')
        pub.subscribe(self.on_paste_from_clipboard, 'PASTE_FROM_CLIPBOARD')
        pub.subscribe(self.on_load_and_paste_from_clipboard, 'LOAD_AND_PASTE_FROM_CLIPBOARD')

        pub.subscribe(self.on_new, 'NEW_FILE')
        pub.subscribe(self.on_open, 'OPEN_FILE')
        pub.subscribe(self.on_save, 'SAVE_FILE')
        pub.subscribe(self.on_save_as, 'SAVE_AS_FILE')

        pub.subscribe(self.on_cut, 'CUT')
        pub.subscribe(self.on_copy, 'COPY')
        # pub.subscribe(self.on_paste, 'PASTE')
        pub.subscribe(self.on_delete, 'DELETE')

        # open/save grid from/to file
        pub.subscribe(self.on_read_from_file, 'READ_FROM_FILE')
        pub.subscribe(self.on_write_to_file, 'WRITE_TO_FILE')

    def show_all(self):
        self.gui.show_all()

    def on_undo(self):

        def cut_symbol():
            self.remove_from_objects(symbol)
            symbol.remove(self.grid)

        def paste_symbol():
            self.objects.append(symbol)
            symbol.paste(self.grid)

        if len(self.last_action) > 0:

            action, symbol = self.last_action.pop()

            if action == REMOVE:
                paste_symbol()

            elif action == INSERT:
                cut_symbol()

        else:
            # no more actions to undo
            pub.sendMessage('UNDO_CHANGED', undo=False)  # TODO enable undo (in each paste_xxxx method?)

    # File menu

    def on_new(self):
        self.grid = Grid(72, 36)
        pub.sendMessage('GRID', grid=self.grid)

    def on_open(self):
        dialog = FileChooserWindow(open=True)  # noqa: F841

    def on_save(self):
        if self.filename is not None:
            self.on_write_to_file(self.filename)

    def on_save_as(self):
        dialog = FileChooserWindow()  # noqa: F841

    # Edit menu

    def remove_from_objects(self, symbol):
        for idx, sym in enumerate(self.objects):
            if id(sym) == id(symbol):
                del self.objects[idx]
                break

    def find_selected(self, rect):
        """Select all symbols that are located within the selection rectangle."""

        ul, br = rect

        selected = []
        for symbol in self.objects:

            # select symbols of which the upper-left corner is within the selection rectangle
            if symbol.startpos.in_rect(rect):
                symbolview = symbol.view
                selection = SelectedObjects(startpos=ul, symbol=symbol, view=symbolview)
                selected.append(selection)

        self.selected_objects = selected

    def on_cut(self, rect):

        self.find_selected(rect)

        action = []
        for sel in self.selected_objects:

            act = Action(action=REMOVE, symbol=sel.symbol)
            action.append(act)

            sel.symbol.remove(self.grid)
            self.remove_from_objects(sel.symbol)

        self.last_action += action

        pub.sendMessage('NOTHING_SELECTED')

    def on_copy(self, rect):
        """Select all symbols that are located within the selection rectangle."""

        self.find_selected(rect)

        pub.sendMessage('OBJECTS_SELECTED', objects=self.selected_objects)

    def on_delete(self, rect):

        self.find_selected(rect)

        for sel in self.selected_objects:
            sel.symbol.remove(self.grid)
            self.remove_from_objects(sel.symbol)

        pub.sendMessage('NOTHING_SELECTED')

    # grid manipulation

    def on_grid_col(self, col, action):

        symbol = Column(col, action)
        self.objects.append(symbol)

        act = Action(action=action, symbol=symbol)
        self.last_action.append(act)

        if action == INSERT:
            self.grid.insert_col(col)
        else:
            self.grid.remove_col(col)

    def on_grid_row(self, row, action):

        symbol = Row(row, action)
        self.objects.append(symbol)

        act = Action(action=action, symbol=symbol)
        self.last_action.append(act)

        if action == INSERT:
            self.grid.insert_row(row)
        else:
            self.grid.remove_row(row)

    # character/component symbol

    def on_character_changed(self, char):
        self.symbol = Character(char)
        pub.sendMessage('CHARACTER_SELECTED', char=self.symbol)

    def on_component_changed(self, label):
        self.selected_objects = []
        self.symbol = self.components.get_symbol(label)
        pub.sendMessage('SYMBOL_SELECTED', symbol=self.symbol)

    def on_rotate_symbol(self):
        # only components can be rotated
        if len(self.selected_objects) == 0:
            self.symbol.grid_next()
            pub.sendMessage('SYMBOL_SELECTED', symbol=self.symbol)
        # else:
        #     for sel in self.selected_objects:
        #         sel.symbol.grid_next()

    def on_mirror_symbol(self):
        self.symbol.mirrored = 1 - self.symbol.mirrored  # toggle 0/1
        pub.sendMessage('SYMBOL_SELECTED', symbol=self.symbol)

    def on_paste_symbol(self, pos):

        symbol = self.symbol.copy()
        symbol.startpos = pos

        self.objects.append(symbol)

        symbol.paste(self.grid)

    def on_paste_character(self, pos):

        symbol = self.symbol.copy()
        symbol.startpos = pos

        self.objects.append(symbol)

        symbol.paste(self.grid)

    def on_paste_text(self, pos, text):

        self.symbol = Text(pos, text)

        self.objects.append(self.symbol)

        self.symbol.paste(self.grid)

    def on_paste_objects(self, pos):
        """
        Paste multiple selection.
        :param pos: the target position in grid (col, row) coordinates.
        """

        def classname(x):
            return type(x).__name__

        action = []

        for sel in self.selected_objects:

            offset = pos - sel.startpos

            # TODO make the position translation a Symbol method
            symbol = sel.symbol.copy()
            symbol.startpos += offset
            symbol.endpos += offset

            if classname(symbol) == 'MagLine':  # FIXME
                symbol.ml_endpos += offset

            act = Action(action=INSERT, symbol=symbol)
            action.append(act)

            self.objects.append(symbol)

            symbol.paste(self.grid)

        self.last_action += action

        pub.sendMessage('NOTHING_SELECTED')

    def on_cut_objects(self, rect):

        action = []

        for sel in self.selected_objects:

            act = Action(action=REMOVE, symbol=symbol)
            action.append(act)

            self.remove_from_objects(sel.symbol)

            grid = sel.symbol.grid
            dummy, rect = grid.rect()

            self.grid.erase_rect(rect)

        self.last_action += action

        pub.sendMessage('NOTHING_SELECTED')

    # lines

    def on_paste_line(self, startpos, endpos, type):

        self.symbol = Line(startpos, endpos, type)

        self.objects.append(self.symbol)

        self.symbol.paste(self.grid)

    def on_paste_mag_line(self, startpos, endpos, ml_endpos):

        self.symbol = MagLine(startpos, endpos, ml_endpos)

        self.objects.append(self.symbol)

        self.symbol.paste(self.grid)

    def on_paste_rect(self, startpos, endpos):

        self.symbol = Rect(startpos, endpos)

        self.objects.append(self.symbol)

        self.symbol.paste(self.grid)

    # clipboard

    def on_copy_to_clipboard(self):
        self.grid.copy_to_clipboard()

    def on_paste_from_clipboard(self):
        self.grid.paste_from_clipboard()
        pub.sendMessage('GRID', grid=self.grid)

    def on_load_and_paste_from_clipboard(self):
        self.grid.load_and_paste_from_clipboard()
        pub.sendMessage('GRID', grid=self.grid)

    # other

    def on_select_rect(self):
        """Select multiple objects."""
        pub.sendMessage('SELECTING_RECT', objects=self.objects)

    def on_select_objects(self):
        """Select individual objects."""
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
        except IOError:
            print(_("Unable to open file for writing: %s" % filename))

    def on_read_from_file(self, filename):
        self.filename = filename
        try:
            file = open(filename, 'r')
            str = file.readlines()

            memo = []
            for line in str:
                memo.append(line)

            pub.sendMessage('FILE_OPENED')

            file.close()

            self.grid = Grid(72, 36)  # the ASCII grid
            pub.sendMessage('GRID', grid=self.grid)

            skipped = self.play_memo(memo)
            if skipped > 0:
                print("{0} lines skipped in file {1}".format(skipped, filename))

        except (IOError, UnicodeDecodeError):
            print(_("Unable to open file for reading: %s" % filename))

    def play_memo(self, memo):

        for item in memo:

            m1 = re.search('(^comp|^char|^rect|^line|^mline):(\d+),(\d+),(\d+),?(\d*),?(\d*),?(\d*)', item)  # noqa W605
            m2 = re.search('(^d|^i)(row|col):(\d+)', item)  # noqa W605
            m3 = re.search('(^text):(\d+),(\d+),(.*)', item)  # noqa W605

            skipped = 0

            if m1 is not None:
                self.play_m1(m1, skipped)
            elif m2 is not None:
                self.play_m2(m2, skipped)
            elif m3 is not None:
                self.play_m3(m3, skipped)
            else:
                skipped += 1

        return skipped

    def play_m1(self, m, skipped):

        # print("regexp groups:")
        # for grp in m.groups():
        #     print(grp)

        type = m.group(1)

        if type == COMPONENT:

            id = m.group(2)
            orientation = int(m.group(3))
            mirrored = int(m.group(4))

            x, y = m.group(5, 6)
            pos = Pos(x, y)

            # print("MEMO: {0} pos: ({1},{2})".format(item, x, y))

            self.symbol = self.components.get_symbol_byid(id)
            self.symbol.ori = orientation
            self.symbol.mirrored = mirrored

            self.on_paste_symbol(pos)

        elif type == CHARACTER:

            ascii = m.group(2)
            char = chr(int(ascii))

            x, y = m.group(3, 4)
            pos = Pos(x, y)

            self.symbol = Character(char)
            self.on_paste_character(pos)

        elif type == LINE:

            terminal = m.group(2)

            x, y = m.group(3, 4)
            startpos = Pos(x, y)

            x, y = m.group(5, 6)
            endpos = Pos(x, y)

            self.on_paste_line(startpos, endpos, terminal)

        elif type == MAG_LINE:

            x, y = m.group(2, 3)
            startpos = Pos(x, y)

            x, y = m.group(4, 5)
            endpos = Pos(x, y)

            x, y = m.group(6, 7)
            ml_endpos = Pos(x, y)

            self.on_paste_mag_line(startpos, endpos, ml_endpos)

        elif type == DRAW_RECT:

            x, y = m.group(2, 3)
            startpos = Pos(x, y)

            x, y = m.group(4, 5)
            endpos = Pos(x, y)

            self.on_paste_rect(startpos, endpos)

        else:
            skipped += 1

    def play_m2(self, m, skipped):

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
            skipped += 1

    def play_m3(self, m, skipped):

        type = m.group(1)

        if type == TEXT:

            x, y = m.group(2, 3)
            startpos = Pos(x, y)

            str = m.group(4)
            text = json.loads(str)

            self.on_paste_text(startpos, text)

        else:
            skipped += 1
