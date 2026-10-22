from concurrent.futures import ThreadPoolExecutor
from app.db import Databases


def test_request_connection_can_move_between_worker_threads(tmp_path):
    databases = Databases(tmp_path)
    with ThreadPoolExecutor(max_workers=1) as worker:
        conn = worker.submit(databases.control).result()
    try:
        assert conn.execute("select count(*) from tenant").fetchone()[0] == 0
    finally:
        conn.close()
