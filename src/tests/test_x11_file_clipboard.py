import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from Xlib import X

from cinnamon_clipboard.core import x11_file_clipboard
from cinnamon_clipboard.core.x11_file_clipboard import X11FileClipboard

TIMESTAMP_ATOM = 500
WINDOW_ID = 42


class FakeDisplay:
    """Minimal python-xlib display that replays a prepared list of events."""

    def __init__(self, events):
        self.events = list(events)

    def pending_events(self):
        return len(self.events)

    def next_event(self):
        return self.events.pop(0)

    def flush(self):
        pass

    def get_selection_owner(self, selection):
        return SimpleNamespace(id=WINDOW_ID)


def property_notify(server_time):
    return SimpleNamespace(
        type=X.PropertyNotify,
        atom=TIMESTAMP_ATOM,
        time=server_time,
    )


class TestX11FileClipboardTimestamp(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.old_file = Path(self.temp_dir.name) / "old.txt"
        self.new_file = Path(self.temp_dir.name) / "new.txt"
        self.old_file.write_text("old", encoding="utf-8")
        self.new_file.write_text("new", encoding="utf-8")

    def make_clipboard(self, events):
        # Bypass __init__ so no real X server connection is needed.
        clipboard = X11FileClipboard.__new__(X11FileClipboard)
        clipboard.display = FakeDisplay(events)
        clipboard.window = Mock(id=WINDOW_ID)
        clipboard.clipboard = 1
        clipboard._timestamp_property = TIMESTAMP_ATOM
        clipboard._paths = [str(self.old_file)]
        clipboard._timestamp = 0
        clipboard._io_watch_id = None
        clipboard._start_event_processing = Mock()
        return clipboard

    def test_request_during_wait_is_answered_with_previous_files(self):
        request = SimpleNamespace(type=X.SelectionRequest)
        clipboard = self.make_clipboard([request, property_notify(1234)])

        answered_paths = []
        clipboard._handle_selection_request = Mock(
            side_effect=lambda req: answered_paths.append(list(clipboard._paths))
        )

        self.assertTrue(clipboard.set_files([str(self.new_file)]))

        clipboard._handle_selection_request.assert_called_once_with(request)
        self.assertEqual(answered_paths, [[str(self.old_file)]])
        self.assertEqual(clipboard._paths, [str(self.new_file)])

    def test_server_timestamp_is_used_for_ownership(self):
        clipboard = self.make_clipboard([property_notify(1234)])

        self.assertTrue(clipboard.set_files([str(self.new_file)]))

        self.assertEqual(clipboard._timestamp, 1234)
        clipboard.window.set_selection_owner.assert_called_once_with(1, 1234)
        clipboard._start_event_processing.assert_called_once()

    def test_timeout_keeps_previous_files(self):
        clipboard = self.make_clipboard([])

        with patch.object(
            x11_file_clipboard.time, "monotonic", side_effect=[0.0, 1.0]
        ), patch.object(x11_file_clipboard.select, "select") as fake_select:
            self.assertFalse(clipboard.set_files([str(self.new_file)]))

        fake_select.assert_not_called()
        self.assertEqual(clipboard._paths, [str(self.old_file)])
        clipboard.window.set_selection_owner.assert_not_called()

    def test_wait_uses_select_until_timestamp_arrives(self):
        clipboard = self.make_clipboard([])

        def deliver_timestamp(*args):
            clipboard.display.events.append(property_notify(99))
            return ([clipboard.display], [], [])

        with patch.object(
            x11_file_clipboard.select, "select", side_effect=deliver_timestamp
        ) as fake_select:
            self.assertEqual(clipboard._get_server_timestamp(), 99)

        fake_select.assert_called_once()

    def test_selection_clear_during_wait_stops_event_processing(self):
        clear = SimpleNamespace(type=X.SelectionClear)
        clipboard = self.make_clipboard([clear, property_notify(1234)])
        clipboard._stop_event_processing = Mock()

        self.assertEqual(clipboard._get_server_timestamp(), 1234)
        clipboard._stop_event_processing.assert_called_once()


if __name__ == "__main__":
    unittest.main()
