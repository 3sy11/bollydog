import signal
from typing import Iterable, Any

import mode


class Bootstrap(mode.Worker):
    supervisor = mode.OneForOneSupervisor()

    def on_init_dependencies(self) -> Iterable[mode.ServiceT]:
        return self.services

    async def on_first_start(self) -> None:

        # < 启动前打印各项资源对象和资源类
        # < 初始化日志
        # < 初始化监控aiomonitor
        self.install_signal_handlers()
        await super(Bootstrap, self).on_first_start()

    async def on_start(self) -> None:
        """Called when the worker starts."""
        pass

    async def on_started(self) -> None:
        """Called when the worker has started."""
        await super(Bootstrap, self).on_started()

    def on_worker_shutdown(self) -> None:
        """Called when the worker is shutting down."""
        # # execute_from_commandline()中的finally中调用
        pass

    def stop_and_shutdown(self) -> None:
        """Stop the worker and shutdown the event loop."""
        # # execute_from_commandline()中的finally中调用
        super(Bootstrap, self).stop_and_shutdown()

    def _on_sigint(self) -> None:
        # self.carp("-INT- -INT- -INT- -INT- -INT- -INT-")
        self.logger.info('-EXIT- -EXIT- -EXIT- -EXIT- -EXIT- -EXIT-')
        self._schedule_shutdown(signal.SIGINT)

    def _log_mundane(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """
        set stack level 3 to log right stack frame
        """
        self.log.log(self._mundane_level, msg, stacklevel=3, *args, **kwargs)


# < 注册到数据中心
