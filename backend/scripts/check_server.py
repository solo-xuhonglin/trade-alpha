"""Check if the backend server is running."""
import urllib.request
import urllib.error
import sys


def check_server(host: str = "localhost", port: int = 8000) -> bool:
    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if response.status == 200:
                data = response.read().decode("utf-8")
                print(f"✓ Server is running at http://{host}:{port}")
                print(f"  Response: {data}")
                return True
    except urllib.error.URLError as e:
        print(f"✗ Server is not running at http://{host}:{port}")
        print(f"  Error: {e.reason}")
        return False
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return False


if __name__ == "__main__":
    host = "localhost"
    port = 8000

    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        port = int(sys.argv[2])

    success = check_server(host, port)
    sys.exit(0 if success else 1)
