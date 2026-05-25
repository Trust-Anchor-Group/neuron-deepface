import io
import logging
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from deepface.commons.logger import Logger

logger = Logger()


def test_singleton_same_object():
    assert Logger() == Logger()
    logger.info("✅ id's of instances of \"singletoned\" class Logger are the same")


def test_logger_writes_hourly_xml_file(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPFACE_LOG_DIR", str(tmp_path))
    logger.log_level = logging.INFO
    logger._console_stdout = io.StringIO()
    logger._console_stderr = io.StringIO()

    expected_log_file = Path(logger._get_log_file_path(datetime.now()))
    logger.info("singleton xml test")

    assert expected_log_file.exists()

    tree = ET.parse(expected_log_file)
    root = tree.getroot()
    namespace = {"eo": Logger.XML_NAMESPACE}
    message_row = root.find("./eo:Informational/eo:Message/eo:Row", namespace)

    assert root.tag == f"{{{Logger.XML_NAMESPACE}}}EventOutput"
    assert message_row is not None
    assert message_row.text == "singleton xml test"


def test_logger_mirrors_direct_info_to_stdout(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPFACE_LOG_DIR", str(tmp_path))
    logger.log_level = logging.INFO
    logger._console_stdout = io.StringIO()
    logger._console_stderr = io.StringIO()

    expected_log_file = Path(logger._get_log_file_path(datetime.now()))
    logger.info("startup line test")

    assert logger._console_stdout.getvalue() == "startup line test\n"
    assert logger._console_stderr.getvalue() == ""
    assert expected_log_file.exists()

    tree = ET.parse(expected_log_file)
    root = tree.getroot()
    namespace = {"eo": Logger.XML_NAMESPACE}
    message_rows = root.findall("./eo:Informational/eo:Message/eo:Row", namespace)

    assert any(row.text == "startup line test" for row in message_rows)


def test_stream_interceptor_mirrors_output_to_xml(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPFACE_LOG_DIR", str(tmp_path))
    logger.log_level = logging.INFO

    captured_stdout = io.StringIO()
    interceptor = Logger._StreamInterceptor(
        logger=logger,
        stream=captured_stdout,
        event_type="Informational",
        level="Minor",
    )

    expected_log_file = Path(logger._get_log_file_path(datetime.now()))
    interceptor.write("stdout mirror test")
    interceptor.write("\n")
    interceptor.flush()

    assert captured_stdout.getvalue() == "stdout mirror test\n"
    assert expected_log_file.exists()

    tree = ET.parse(expected_log_file)
    root = tree.getroot()
    namespace = {"eo": Logger.XML_NAMESPACE}
    message_rows = root.findall("./eo:Informational/eo:Message/eo:Row", namespace)

    assert any(row.text == "stdout mirror test" for row in message_rows)


def test_logger_falls_back_to_console_when_log_file_is_locked_on_read(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPFACE_LOG_DIR", str(tmp_path))
    logger.log_level = logging.INFO
    logger._console_stdout = io.StringIO()
    logger._console_stderr = io.StringIO()

    expected_log_file = Path(logger._get_log_file_path(datetime.now()))
    expected_log_file.parent.mkdir(parents=True, exist_ok=True)
    expected_log_file.write_text("<locked />", encoding="utf-8")

    original_parse = ET.parse

    def locked_parse(source, parser=None):
        if Path(source) == expected_log_file:
            raise PermissionError("The process cannot access the file because it is being used by another process")
        return original_parse(source, parser=parser)

    monkeypatch.setattr(ET, "parse", locked_parse)

    logger.info("locked read test")

    assert logger._console_stdout.getvalue() == "locked read test\n"
    assert "Logger file write failed for" in logger._console_stderr.getvalue()
    assert str(expected_log_file) in logger._console_stderr.getvalue()


def test_logger_falls_back_to_console_when_log_file_is_locked_on_write(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPFACE_LOG_DIR", str(tmp_path))
    logger.log_level = logging.INFO
    logger._console_stdout = io.StringIO()
    logger._console_stderr = io.StringIO()

    original_write = ET.ElementTree.write

    def locked_write(self, file_or_filename, *args, **kwargs):
        if Path(file_or_filename) == Path(logger._get_log_file_path(datetime.now())):
            raise PermissionError("The process cannot access the file because it is being used by another process")
        return original_write(self, file_or_filename, *args, **kwargs)

    monkeypatch.setattr(ET.ElementTree, "write", locked_write)

    logger.info("locked write test")

    assert logger._console_stdout.getvalue() == "locked write test\n"
    assert "Logger file write failed for" in logger._console_stderr.getvalue()
