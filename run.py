"""Jalankan kedua service lokal dengan satu perintah: python run.py"""

import signal
import subprocess
import sys
import time
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    processes = []

    def stop(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    print("Starting Karhutla Sentiment…", flush=True)
    print("Dashboard: http://127.0.0.1:8501", flush=True)
    print("API docs:  http://127.0.0.1:8000/docs", flush=True)
    print("Press Ctrl+C to stop both services.", flush=True)
    try:
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "karhutla.api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                cwd=root,
            )
        )
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "streamlit",
                    "run",
                    "app.py",
                    "--server.address",
                    "127.0.0.1",
                    "--server.headless",
                    "true",
                ],
                cwd=root,
            )
        )
        while all(process.poll() is None for process in processes):
            time.sleep(0.5)
        print("A service stopped. Check the messages above (ports 8000/8501 may be in use).")
        return 1
    except KeyboardInterrupt:
        print("\nStopping both services…", flush=True)
        return 0
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    sys.exit(main())
