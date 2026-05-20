import logging
import sys

try:
    from gunicorn import glogging
except ModuleNotFoundError:
    glogging = None

from deepface.commons.logger import Logger


class _MissingGunicornLogger:
    def __init__(self, *args, **kwargs) -> None:
        raise ModuleNotFoundError(
            "gunicorn must be installed to use DeepFaceGunicornLogger"
        )


BaseGunicornLogger = _MissingGunicornLogger if glogging is None else glogging.Logger


class _DeepFaceGunicornHandler(logging.Handler):
    def __init__(
        self,
        deepface_logger: Logger,
        stream,
        is_access_log: bool = False,
    ) -> None:
        super().__init__()
        self.deepface_logger = deepface_logger
        self.stream = stream
        self.is_access_log = is_access_log

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            if message == "":
                return

            self.stream.write(message + "\n")
            self.stream.flush()
            self._write_to_deepface_logger(record, message)
        except Exception:
            self.handleError(record)

    def _write_to_deepface_logger(self, record: logging.LogRecord, message: str) -> None:
        event_type = "Informational"
        level = "Minor"

        if self.is_access_log:
            event_type = "Informational"
            level = "Minor"
        elif record.levelno >= logging.CRITICAL:
            event_type = "Critical"
            level = "Critical"
        elif record.levelno >= logging.ERROR:
            event_type = "Error"
            level = "Major"
        elif record.levelno >= logging.WARNING:
            event_type = "Warning"
            level = "Minor"
        elif record.levelno >= logging.INFO:
            event_type = "Informational"
            level = "Minor"
        else:
            event_type = "Debug"
            level = "Minor"

        self.deepface_logger.dump_log(
            message,
            event_type=event_type,
            level=level,
            mirror_to_console=False,
        )


class DeepFaceGunicornLogger(BaseGunicornLogger):
    def setup(self, cfg) -> None:
        self.loglevel = self.LOG_LEVELS.get(cfg.loglevel.lower(), logging.INFO)
        self.error_log.setLevel(self.loglevel)
        self.access_log.setLevel(logging.INFO)

        self.error_log.handlers = []
        self.access_log.handlers = []
        self.error_log.propagate = False
        self.access_log.propagate = False

        deepface_logger = Logger()
        formatter = logging.Formatter("%(message)s")

        error_handler = _DeepFaceGunicornHandler(
            deepface_logger=deepface_logger,
            stream=sys.__stderr__,
        )
        error_handler.setFormatter(formatter)
        self.error_log.addHandler(error_handler)

        access_handler = _DeepFaceGunicornHandler(
            deepface_logger=deepface_logger,
            stream=sys.__stdout__,
            is_access_log=True,
        )
        access_handler.setFormatter(formatter)
        self.access_log.addHandler(access_handler)