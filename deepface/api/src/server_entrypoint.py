import os
import shlex
import sys
from typing import List

from deepface.commons.logger import Logger


DEFAULT_ACCESS_LOG_FORMAT = '%(h)s - - [%(t)s] "%(r)s" %(s)s %(b)s %(L)s'


def build_gunicorn_command(extra_args: List[str]) -> List[str]:
    command = [
        "gunicorn",
        f"--workers={os.getenv('DEEPFACE_GUNICORN_WORKERS', '1')}",
        f"--timeout={os.getenv('DEEPFACE_GUNICORN_TIMEOUT', '7200')}",
        f"--bind={os.getenv('DEEPFACE_GUNICORN_BIND', '0.0.0.0:5000')}",
        f"--log-level={os.getenv('DEEPFACE_GUNICORN_LOG_LEVEL', 'debug')}",
        "--logger-class=deepface.api.src.gunicorn_logger.DeepFaceGunicornLogger",
        f"--access-logformat={os.getenv('DEEPFACE_GUNICORN_ACCESS_LOGFORMAT', DEFAULT_ACCESS_LOG_FORMAT)}",
        "--access-logfile=-",
        os.getenv("DEEPFACE_GUNICORN_APP", "deepface.api.src.app:create_app()"),
    ]

    extra_cli_args = os.getenv("DEEPFACE_GUNICORN_EXTRA_ARGS", "")
    if extra_cli_args.strip() != "":
        command.extend(shlex.split(extra_cli_args))

    command.extend(extra_args)
    return command


def main() -> None:
    Logger().info("Starting the application...")
    command = build_gunicorn_command(sys.argv[1:])
    os.execvp(command[0], command)


if __name__ == "__main__":
    main()