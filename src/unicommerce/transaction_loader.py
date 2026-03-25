"""
Transaction loader — upserts normalized transaction rows into the database.

All UC data types (dispatches, returns, GRNs) are normalized into the same
transactions table format before calling load_transactions().
"""
import logging
import psycopg2.extras

logger = logging.getLogger(__name__)


def load_transactions(db_conn, txns):
    """
    Upsert transaction rows into the transactions table.

    Uses (voucher_number, stock_item_name, is_inward) as idempotency key.
    If a transaction is pulled twice, the second write updates the row.

    Args:
        db_conn: PostgreSQL connection
        txns: List of transaction dicts with keys:
            txn_date, stock_item_name, quantity, is_inward, channel,
            uc_channel, party_name, voucher_type, voucher_number,
            rate, amount, return_type, facility, shipping_package_code

    Returns:
        Number of rows upserted
    """
    if not txns:
        return 0

    sql = """
        INSERT INTO transactions
            (txn_date, stock_item_name, quantity, is_inward, channel,
             uc_channel, party_name, voucher_type, voucher_number,
             rate, amount, return_type, facility, shipping_package_code)
        VALUES
            (%(txn_date)s, %(stock_item_name)s, %(quantity)s, %(is_inward)s, %(channel)s,
             %(uc_channel)s, %(party_name)s, %(voucher_type)s, %(voucher_number)s,
             %(rate)s, %(amount)s, %(return_type)s, %(facility)s, %(shipping_package_code)s)
        ON CONFLICT (voucher_number, stock_item_name, is_inward) DO UPDATE SET
            txn_date = EXCLUDED.txn_date,
            quantity = EXCLUDED.quantity,
            channel = EXCLUDED.channel,
            uc_channel = EXCLUDED.uc_channel,
            return_type = EXCLUDED.return_type,
            facility = EXCLUDED.facility
    """
    with db_conn.cursor() as cur:
        psycopg2.extras.execute_batch(cur, sql, txns, page_size=1000)
    db_conn.commit()

    logger.info("Upserted %d transactions", len(txns))
    return len(txns)
