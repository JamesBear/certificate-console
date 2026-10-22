from contextlib import closing
import sqlite3
from app.bootstrap import ensure_demo_data


def test_empty_control_file_is_seeded_and_restart_preserves_changes(tmp_path):
    marker = tmp_path / "unrelated.txt"
    marker.write_text("preserve")
    control = tmp_path / "control.db"
    sqlite3.connect(control).close()
    assert ensure_demo_data(tmp_path)
    assert marker.read_text() == "preserve"
    with closing(sqlite3.connect(control)) as conn:
        conn.execute("update tenant set name='Persistent tenant' where code='ACM'")
        conn.commit()
    assert not ensure_demo_data(tmp_path)
    with closing(sqlite3.connect(control)) as conn:
        assert conn.execute("select name from tenant where code='ACM'").fetchone()[0] == 'Persistent tenant'
