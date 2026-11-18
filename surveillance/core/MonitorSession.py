import logging
from copy import deepcopy


logger = logging.getLogger('l_default')


class MonitorSession:
    """Keep the controller alive and rebuild playback when monitors change."""

    def __init__(self, manager_factory, enable_caching_next_screen):
        self.manager_factory = manager_factory
        self.enable_caching_next_screen = enable_caching_next_screen
        self.monitors = None
        self.managers = []

    def stop(self):
        # The first manager owns pygame; destroy it after the other managers.
        for manager in reversed(self.managers):
            manager.destroy()
        self.managers.clear()
        self.monitors = None

    def update(self, monitors):
        if monitors == self.monitors:
            return

        self.stop()
        if not monitors:
            logger.info('No active monitor; display controller is waiting for a screen')
            self.monitors = []
            return

        try:
            for index, monitor in enumerate(monitors):
                manager = self.manager_factory(
                    f'screen_manager_{index}', monitor,
                    self.enable_caching_next_screen, index != 0,
                )
                self.managers.append(manager)
            for manager in self.managers:
                manager.bootstrap()
        except Exception:
            self.stop()
            raise

        self.monitors = deepcopy(monitors)
        logger.info('Display playback started for %d monitor(s)', len(monitors))
