"""The demo server must keep responding after its access log exceeds pipe capacity."""
import urllib.request


def test_server_stays_responsive_after_many_requests(base_url):
    for _ in range(256):
        with urllib.request.urlopen(base_url + "/api/health", timeout=2) as response:
            assert response.status == 200
