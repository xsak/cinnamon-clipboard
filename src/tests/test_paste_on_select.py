import unittest
from types import SimpleNamespace
from unittest.mock import patch

from Xlib import XK, X

from cinnamon_clipboard.core import clipboard
from cinnamon_clipboard.core.clipboard import ClipboardManager

KEYCODES = {XK.XK_Control_L: 37, XK.XK_Shift_L: 50, XK.XK_v: 55}


class FakeWindow:
    """python-xlib window with a parent, enough for query_tree and get_wm_class."""

    def __init__(self, xid, parent=None, wm_class=None):
        self.id = xid
        self.parent = parent
        self.wm_class = wm_class

    def query_tree(self):
        root = self
        while root.parent is not None:
            root = root.parent
        # The root window has no parent; python-xlib reports that as 0.
        return SimpleNamespace(root=root, parent=self.parent or 0)

    def get_wm_class(self):
        return self.wm_class


class FakeDisplay:
    """Display whose focus follows a prepared list, one entry per get_input_focus call."""

    def __init__(self, focus_sequence, held_keycode=None):
        self.focus_sequence = list(focus_sequence)
        self.held_keycode = held_keycode

    def get_input_focus(self):
        focus = self.focus_sequence[0]
        if len(self.focus_sequence) > 1:
            self.focus_sequence.pop(0)
        return SimpleNamespace(focus=focus)

    def query_keymap(self):
        keymap = [0] * 32
        if self.held_keycode:
            keymap[self.held_keycode >> 3] |= 1 << (self.held_keycode & 7)
        return keymap

    def keysym_to_keycode(self, keysym):
        return KEYCODES.get(keysym, 0)

    def flush(self):
        pass


ROOT = FakeWindow(1)
TARGET = FakeWindow(100, parent=ROOT)          # Muffin frame of the app we were typing in
TARGET_CHILD = FakeWindow(101, parent=TARGET)  # the app's own window that really has focus
OTHER = FakeWindow(200, parent=ROOT)           # e.g. a chat window that popped up
MENU = FakeWindow(300, parent=ROOT)            # the quick menu itself


def make_manager(disp):
    manager = ClipboardManager.__new__(ClipboardManager)
    manager.x11_file_clipboard = SimpleNamespace(display=disp)
    return manager


def run_paste(manager, target_xid, item_type="text"):
    """Run paste_to_active_window with GLib timers executed immediately; return the keys sent."""
    sent = []
    timers = []

    def fake_timeout_add(delay, callback):
        timers.append(callback)
        return len(timers)

    def fake_fake_input(disp, event_type, keycode):
        sent.append((event_type, keycode))

    with patch.object(clipboard.GLib, "timeout_add", side_effect=fake_timeout_add), \
            patch.object(clipboard.xtest, "fake_input", side_effect=fake_fake_input):
        manager.paste_to_active_window(item_type=item_type, target_xid=target_xid)
        while timers:
            timers.pop(0)()
    return sent


CTRL_V = [
    (X.KeyPress, 37),
    (X.KeyPress, 55),
    (X.KeyRelease, 55),
    (X.KeyRelease, 37),
]


class TestToplevelXid(unittest.TestCase):
    def test_child_window_resolves_to_its_toplevel(self):
        manager = make_manager(FakeDisplay([TARGET_CHILD]))
        self.assertEqual(manager.get_focused_toplevel_xid(), TARGET.id)

    def test_no_application_window_gives_none(self):
        # No focus (0), PointerRoot (1) and the root window itself.
        for focus in (0, 1, ROOT):
            manager = make_manager(FakeDisplay([focus]))
            self.assertIsNone(manager.get_focused_toplevel_xid(), focus)


class TestPasteOnSelect(unittest.TestCase):
    def test_pastes_when_focus_is_on_target(self):
        manager = make_manager(FakeDisplay([TARGET_CHILD]))
        self.assertEqual(run_paste(manager, TARGET.id), CTRL_V)

    def test_waits_until_focus_returns_to_target(self):
        manager = make_manager(FakeDisplay([MENU, MENU, OTHER, TARGET_CHILD]))
        self.assertEqual(run_paste(manager, TARGET.id), CTRL_V)

    def test_cancels_when_focus_stays_on_another_window(self):
        manager = make_manager(FakeDisplay([OTHER]))
        self.assertEqual(run_paste(manager, TARGET.id), [])

    def test_cancels_when_keys_stay_held(self):
        manager = make_manager(FakeDisplay([TARGET_CHILD], held_keycode=KEYCODES[XK.XK_Control_L]))
        self.assertEqual(run_paste(manager, TARGET.id), [])

    def test_no_target_copies_only(self):
        manager = make_manager(FakeDisplay([TARGET_CHILD]))
        self.assertEqual(run_paste(manager, None), [])

    def test_terminal_target_gets_ctrl_shift_v(self):
        terminal = FakeWindow(400, parent=ROOT, wm_class=("gnome-terminal-server", "Gnome-terminal"))
        manager = make_manager(FakeDisplay([terminal]))
        self.assertEqual(run_paste(manager, terminal.id), [
            (X.KeyPress, 37),
            (X.KeyPress, 50),
            (X.KeyPress, 55),
            (X.KeyRelease, 55),
            (X.KeyRelease, 50),
            (X.KeyRelease, 37),
        ])


if __name__ == "__main__":
    unittest.main()
