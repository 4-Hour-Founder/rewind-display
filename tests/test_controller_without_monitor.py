import logging
import runpy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'surveillance'))


class ControllerWithoutMonitorTests(unittest.TestCase):
    def run_controller(self, inventories, ticks):
        logger = Mock(spec=logging.Logger)
        factory = Mock()
        managers = [Mock(), Mock()]
        for manager in managers:
            manager.get_disable_autorotation.return_value = True
            manager.get_background_drawinstance.return_value.check_input.return_value = None
        factory.side_effect = managers
        xdisplay = Mock()
        xdisplay.get_atom_name.return_value = 'HDMI-2'
        root = xdisplay.screen.return_value.root
        root.xrandr_get_monitors.side_effect = [
            SimpleNamespace(monitors=items) for items in inventories
        ]
        display_module = SimpleNamespace(Display=Mock(return_value=xdisplay))
        modules = {
            'Xlib': SimpleNamespace(display=display_module),
            'Xlib.display': display_module,
            'core.ScreenManager': SimpleNamespace(ScreenManager=factory),
            'core.util.config': SimpleNamespace(cfg={'advanced': {}}),
            'core.util.setuplogging': SimpleNamespace(setup_logging=lambda: logger),
        }
        with patch.dict(sys.modules, modules), patch('signal.signal'), patch(
            'time.sleep', side_effect=[None] * (ticks - 1) + [SystemExit(0)]
        ):
            with self.assertRaises(SystemExit) as exit_result:
                runpy.run_path(str(ROOT / 'surveillance/surveillance.py'), run_name='__main__')
        self.assertEqual(exit_result.exception.code, 0)
        logger.error.assert_not_called()
        return factory, managers, xdisplay

    def test_main_loop_keeps_running_without_any_monitor(self):
        factory, _, display = self.run_controller([[], [], []], ticks=5)
        factory.assert_not_called()
        self.assertEqual(display.close.call_count, 3)

    def test_main_loop_starts_stops_and_resumes_after_monitor_hotplug(self):
        screen = SimpleNamespace(name=1, width_in_pixels=1920, height_in_pixels=1080, x=0, y=0)
        factory, managers, _ = self.run_controller([[], [screen], [], [screen]], ticks=7)
        self.assertEqual(factory.call_count, 2)
        managers[0].bootstrap.assert_called_once()
        managers[0].destroy.assert_called_once()
        managers[1].bootstrap.assert_called_once()
        managers[1].destroy.assert_not_called()


if __name__ == '__main__':
    unittest.main()
