from unittest.mock import MagicMock
from app.sql_service import SQLUtil


def test_init_db_creates_tables(monkeypatch):
    mock_connect = MagicMock()
    mock_con = MagicMock()
    mock_cur = MagicMock()

    mock_connect.return_value.__enter__.return_value = mock_con
    mock_con.cursor.return_value = mock_cur

    monkeypatch.setattr("app.sql_service.os.path.exists", lambda path: False)
    monkeypatch.setattr("app.sql_service.sqlite3.connect", mock_connect)

    SQLUtil.init_db()

    assert mock_connect.call_count == 2
    mock_connect.assert_any_call("models.db")
    mock_connect.assert_any_call("predictions.db")

    executed_queries = [call.args[0] for call in mock_cur.execute.call_args_list]
    assert any("CREATE TABLE IF NOT EXISTS models" in q for q in executed_queries)
    assert any("CREATE TABLE IF NOT EXISTS PREDICTIONS" in q for q in executed_queries)
