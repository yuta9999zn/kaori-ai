import logging
import sys
from utils.db import get_cursor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("kaori")


def log_etl_run(script, source_file, rows_read, rows_inserted, rows_skipped,
                status="SUCCESS", error_message=None):
    sql = """
        INSERT INTO etl_run_log
            (script, source_file, rows_read, rows_inserted, rows_skipped, status, error_message)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    try:
        with get_cursor() as cur:
            cur.execute(sql, (script, source_file, rows_read, rows_inserted,
                               rows_skipped, status, error_message))
    except Exception as e:
        log.warning(f"Could not write to etl_run_log: {e}")
