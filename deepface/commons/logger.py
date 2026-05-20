import os
import sys
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional, TextIO, Tuple
from xml.etree import ElementTree as ET


ET.register_namespace("", "http://waher.se/Schema/EventOutput.xsd")


# pylint: disable=broad-except
class Logger:
    """
    A Logger class for logging messages with a specific log level.

    The class follows the singleton design pattern, ensuring that only one
    instance of the Logger is created. The parameters of the first instance
    are preserved across all instances. Log entries are appended to an hourly
    XML file that follows the event structure used by the provided samples.
    """

    __instance = None
    XML_NAMESPACE = "http://waher.se/Schema/EventOutput.xsd"

    class _StreamInterceptor:
        def __init__(
            self,
            logger: "Logger",
            stream: TextIO,
            event_type: str,
            level: str,
        ) -> None:
            self._logger = logger
            self._stream = stream
            self._event_type = event_type
            self._level = level
            self._buffer = ""
            self.encoding = getattr(stream, "encoding", "utf-8")

        def write(self, data: str) -> int:
            text = str(data)
            if text == "":
                return 0

            written = self._stream.write(text)
            self._buffer += text
            self._flush_complete_lines()
            return written

        def flush(self) -> None:
            self._flush_buffer()
            self._stream.flush()

        def isatty(self) -> bool:
            return bool(getattr(self._stream, "isatty", lambda: False)())

        def fileno(self) -> int:
            return int(getattr(self._stream, "fileno")())

        def __getattr__(self, attr: str) -> Any:
            return getattr(self._stream, attr)

        def _flush_complete_lines(self) -> None:
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                self._logger._write_intercepted_line(
                    line=line.rstrip("\r"),
                    event_type=self._event_type,
                    level=self._level,
                )

        def _flush_buffer(self) -> None:
            if self._buffer == "":
                return

            self._logger._write_intercepted_line(
                line=self._buffer.rstrip("\r"),
                event_type=self._event_type,
                level=self._level,
            )
            self._buffer = ""

    def __new__(cls) -> "Logger":
        if cls.__instance is None:
            cls.__instance = super(Logger, cls).__new__(cls)
        return cls.__instance

    def __init__(self) -> None:
        if not hasattr(self, "_singleton_initialized"):
            self._singleton_initialized = True  # to prevent multiple initializations
            self._write_lock = threading.RLock()
            self._console_stdout = sys.__stdout__
            self._console_stderr = sys.__stderr__
            log_level = os.environ.get("DEEPFACE_LOG_LEVEL", str(logging.INFO))
            try:
                self.log_level = int(log_level)
            except Exception as err:
                self.dump_log(
                    f"Exception while parsing $DEEPFACE_LOG_LEVEL."
                    f"Expected int but it is {log_level} ({str(err)})."
                    "Setting app log level to info."
                )
                self.log_level = logging.INFO

            self._stdout_interceptor: Optional[Logger._StreamInterceptor] = None
            self._stderr_interceptor: Optional[Logger._StreamInterceptor] = None
            self._install_stream_interceptors()

    def info(self, message: Any) -> None:
        """
        Logs an info message if the log level is set to INFO or lower.
        Args:
            message: The message to log.
        """
        if self.log_level <= logging.INFO:
            self.dump_log(f"{message}", event_type="Informational", level="Minor")

    def debug(self, message: Any) -> None:
        """
        Logs a debug message if the log level is set to DEBUG or lower.
        Args:
            message: The message to log.
        """
        if self.log_level <= logging.DEBUG:
            self.dump_log(f"🕷️ {message}", event_type="Debug", level="Minor")

    def warn(self, message: Any) -> None:
        """
        Logs a warning message if the log level is set to WARNING or lower.
        Args:
            message: The message to log.
        """
        if self.log_level <= logging.WARNING:
            self.dump_log(f"⚠️ {message}", event_type="Warning", level="Minor")

    def error(self, message: Any) -> None:
        """
        Logs an error message if the log level is set to ERROR or lower.
        Args:
            message: The message to log.
        """
        if self.log_level <= logging.ERROR:
            self.dump_log(f"🔴 {message}", event_type="Error", level="Major")

    def critical(self, message: Any) -> None:
        """
        Logs a critical message if the log level is set to CRITICAL or lower.
        Args:
            message: The message to log.
        """
        if self.log_level <= logging.CRITICAL:
            self.dump_log(f"💥 {message}", event_type="Critical", level="Critical")

    def dump_log(
        self,
        message: Any,
        event_type: str = "Informational",
        level: str = "Minor",
        mirror_to_console: bool = True,
    ) -> None:
        """
        Appends the log message to an hourly XML log file.

        Args:
            message: The message to log.
        """
        file_timestamp = datetime.now()
        event_timestamp = datetime.now(timezone.utc)
        log_file_path = self._get_log_file_path(file_timestamp)

        with self._write_lock:
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

            tree, root = self._load_log_tree(log_file_path)
            self._append_event(
                root=root,
                event_type=event_type,
                level=level,
                timestamp=self._format_event_timestamp(event_timestamp),
                message=str(message),
            )
            self._indent_xml(root)
            tree.write(log_file_path, encoding="utf-8", xml_declaration=True)

        if mirror_to_console:
            self._write_console_message(message=str(message), event_type=event_type)

    def _get_log_file_path(self, current_time: datetime) -> str:
        file_name = f"Deepface {current_time.strftime('%Y-%m-%dT%H')}.xml"
        return os.path.join(self._get_log_directory(), file_name)

    def _get_log_directory(self) -> str:
        deepface_home = str(os.getenv("DEEPFACE_HOME", default=os.path.expanduser("~")))
        return str(
            os.getenv(
                "DEEPFACE_LOG_DIR",
                default=os.path.join(deepface_home, ".deepface", "logs"),
            )
        )

    def _load_log_tree(self, log_file_path: str) -> Tuple[ET.ElementTree, ET.Element]:
        if os.path.exists(log_file_path):
            try:
                tree = ET.parse(log_file_path)
                return tree, tree.getroot()
            except ET.ParseError:
                pass

        root = ET.Element(f"{{{self.XML_NAMESPACE}}}EventOutput")
        return ET.ElementTree(root), root

    def _append_event(
        self,
        root: ET.Element,
        event_type: str,
        level: str,
        timestamp: str,
        message: str,
    ) -> None:
        event = ET.SubElement(root, f"{{{self.XML_NAMESPACE}}}{event_type}")
        event.set("timestamp", timestamp)
        event.set("level", level)

        xml_message = ET.SubElement(event, f"{{{self.XML_NAMESPACE}}}Message")
        row = ET.SubElement(xml_message, f"{{{self.XML_NAMESPACE}}}Row")
        row.text = message

    def _format_event_timestamp(self, event_timestamp: datetime) -> str:
        return event_timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _install_stream_interceptors(self) -> None:
        should_capture_streams = os.getenv("DEEPFACE_CAPTURE_STD_STREAMS", "true")
        if should_capture_streams.lower() in {"0", "false", "no"}:
            return

        if self._stdout_interceptor is None and sys.stdout is not None:
            original_stdout = sys.stdout
            self._stdout_interceptor = Logger._StreamInterceptor(
                logger=self,
                stream=original_stdout,
                event_type="Informational",
                level="Minor",
            )
            sys.stdout = self._stdout_interceptor
            self._redirect_stream_handlers(original_stdout, self._stdout_interceptor)

        if self._stderr_interceptor is None and sys.stderr is not None:
            original_stderr = sys.stderr
            self._stderr_interceptor = Logger._StreamInterceptor(
                logger=self,
                stream=original_stderr,
                event_type="Error",
                level="Major",
            )
            sys.stderr = self._stderr_interceptor
            self._redirect_stream_handlers(original_stderr, self._stderr_interceptor)

    def _redirect_stream_handlers(self, source_stream: TextIO, target_stream: TextIO) -> None:
        all_loggers = [logging.getLogger()]
        all_loggers.extend(
            logger
            for logger in logging.root.manager.loggerDict.values()
            if isinstance(logger, logging.Logger)
        )

        for current_logger in all_loggers:
            for handler in current_logger.handlers:
                if isinstance(handler, logging.StreamHandler) and getattr(handler, "stream", None) is source_stream:
                    handler.setStream(target_stream)

    def _write_intercepted_line(self, line: str, event_type: str, level: str) -> None:
        if line.strip() == "":
            return

        self.dump_log(message=line, event_type=event_type, level=level, mirror_to_console=False)

    def _write_console_message(self, message: str, event_type: str) -> None:
        should_mirror_console = os.getenv("DEEPFACE_MIRROR_LOGS_TO_STD_STREAMS", "true")
        if should_mirror_console.lower() in {"0", "false", "no"}:
            return

        stream = self._console_stderr if event_type in {"Error", "Critical"} else self._console_stdout
        stream.write(message + "\n")
        stream.flush()

    def _indent_xml(self, element: ET.Element, level: int = 0) -> None:
        indentation = "\n" + level * "\t"

        if len(element) == 0:
            if level > 0:
                element.tail = indentation
            return

        if not element.text or not element.text.strip():
            element.text = indentation + "\t"

        for child in element:
            self._indent_xml(child, level + 1)

        if not element[-1].tail or not element[-1].tail.strip():
            element[-1].tail = indentation

        if level > 0 and (not element.tail or not element.tail.strip()):
            element.tail = indentation
