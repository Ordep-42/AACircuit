"""
AACircuit
2020-03-02 JvO
"""

import gettext
import locale

# set local language, if supported
try:
    loc = locale.getdefaultlocale()
    lang = loc[0]
    local_lang = gettext.translation('aacircuit', localedir='locale', languages=[lang])
    local_lang.install()
    _ = local_lang.gettext
except OSError:
    _ = gettext.gettext

# grid
FONTSIZE = 12
GRIDSIZE_W = 10
GRIDSIZE_H = 16

# selection action
REMOVE = 'remove'
INSERT = 'insert'
HORIZONTAL = 'hor'
VERTICAL = 'vert'

# selection state
IDLE = 0
SELECTING = 1
SELECTED = 2
DRAG = 3

# selected item
COMPONENT = 'comp'
COL = 'col'
ROW = 'row'
RECT = 'rect'
LINE = 'line'
MAG_LINE = 'mag_line'

# lines
LINE_HOR = '-'
LINE_VERT = '|'
TERMINAL1 = " "
TERMINAL2 = 'o'
TERMINAL3 = '+'
TERMINAL4 = "'"
