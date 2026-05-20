import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


STARTUP_MESSAGE = "Starting the application..."
CONTAINER_LOG_DIR = "/tmp/deepface-logs"
TIMEOUT_SECONDS = 60


def run_command(command, cwd=None, check=True, capture_output=False):
    return subprocess.run(
        command,
        cwd=cwd,
        check=check,
        text=True,
        capture_output=capture_output,
    )


def main() -> int:
    if shutil.which("docker") is None:
        print("Docker CLI is not available.", file=sys.stderr)
        return 1

    repo_root = Path(__file__).resolve().parents[1]
    image_tag = f"deepface-xml-log-check:{uuid.uuid4().hex[:8]}"
    container_name = f"deepface-xml-log-check-{uuid.uuid4().hex[:8]}"

    with tempfile.TemporaryDirectory(prefix="deepface-xml-logs-") as temp_dir:
        host_log_dir = Path(temp_dir)
        try:
            print(f"Building Docker image {image_tag}...")
            run_command(["docker", "build", "-t", image_tag, "."], cwd=repo_root)

            print(f"Starting container {container_name}...")
            run_command(
                [
                    "docker",
                    "run",
                    "--detach",
                    "--name",
                    container_name,
                    "--env",
                    f"DEEPFACE_LOG_DIR={CONTAINER_LOG_DIR}",
                    "--volume",
                    f"{host_log_dir}:{CONTAINER_LOG_DIR}",
                    image_tag,
                ],
                cwd=repo_root,
            )

            deadline = time.time() + TIMEOUT_SECONDS
            while time.time() < deadline:
                log_output = run_command(
                    ["docker", "logs", container_name],
                    cwd=repo_root,
                    capture_output=True,
                ).stdout
                xml_files = sorted(host_log_dir.glob("*.xml"))

                if STARTUP_MESSAGE in log_output and xml_files:
                    latest_xml = xml_files[-1]
                    root = ET.parse(latest_xml).getroot()
                    messages = [element.text for element in root.iter() if element.text]
                    if STARTUP_MESSAGE in "\n".join(messages):
                        print(f"PASS: Found startup line in docker logs and {latest_xml}.")
                        return 0

                time.sleep(2)

            print("FAIL: Startup line was not found in both docker logs and XML log.", file=sys.stderr)
            return 1
        finally:
            run_command(["docker", "rm", "-f", container_name], cwd=repo_root, check=False)
            run_command(["docker", "image", "rm", image_tag], cwd=repo_root, check=False)


if __name__ == "__main__":
    raise SystemExit(main())