import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, call

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'surveillance'))
from core.MonitorSession import MonitorSession


def monitor(width='1920', name='HDMI-2'):
    return {'monitor_id': name, 'resolution': {'width': width, 'height': '1080'}}


class MonitorSessionTests(unittest.TestCase):
    def setUp(self):
        self.factory = Mock()
        self.session = MonitorSession(self.factory, True)

    def test_start_without_tv_stays_idle_then_starts_when_tv_connects(self):
        with self.assertLogs('l_default', level='INFO') as logs:
            self.session.update([])
            self.session.update([])
        self.assertEqual(len(logs.output), 1)
        self.factory.assert_not_called()
        self.assertEqual(self.session.managers, [])

        screen = monitor()
        self.session.update([screen])
        self.factory.assert_called_once_with('screen_manager_0', screen, True, False)
        self.factory.return_value.bootstrap.assert_called_once()

    def test_unplug_stops_players_and_reconnect_rebuilds_playback(self):
        first, second = Mock(), Mock()
        self.factory.side_effect = [first, second]
        self.session.update([monitor()])
        self.session.update([])
        first.destroy.assert_called_once()
        self.assertEqual(self.session.managers, [])
        self.session.update([monitor()])
        second.bootstrap.assert_called_once()
        self.assertEqual(self.session.managers, [second])

    def test_unchanged_monitors_do_not_restart_players(self):
        self.session.update([monitor()])
        self.session.update([monitor()])
        self.factory.assert_called_once()
        self.factory.return_value.destroy.assert_not_called()

    def test_resolution_change_rebuilds_layout(self):
        self.session.update([monitor()])
        self.session.update([monitor('3840')])
        self.assertEqual(self.factory.call_count, 2)
        self.assertEqual(self.session.monitors, [monitor('3840')])

    def test_secondary_monitors_close_before_pygame_owner(self):
        events = Mock()
        first, second = Mock(), Mock()
        events.attach_mock(first, 'first')
        events.attach_mock(second, 'second')
        self.factory.side_effect = [first, second]
        self.session.update([monitor(), monitor(name='HDMI-1')])
        events.reset_mock()
        self.session.stop()
        self.assertEqual(events.mock_calls, [call.second.destroy(), call.first.destroy()])

    def test_failed_bootstrap_cleans_up_and_can_retry(self):
        broken, recovered = Mock(), Mock()
        broken.bootstrap.side_effect = RuntimeError('startup failed')
        self.factory.side_effect = [broken, recovered]
        with self.assertRaises(RuntimeError):
            self.session.update([monitor()])
        broken.destroy.assert_called_once()
        self.assertEqual(self.session.managers, [])
        self.assertIsNone(self.session.monitors)
        self.session.update([monitor()])
        recovered.bootstrap.assert_called_once()


if __name__ == '__main__':
    unittest.main()
