# tests/test_ledger_parser.py
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unicommerce.ledger_parser import parse_ledger_row, is_excluded_entity, classify_channel

def test_picklist_out():
    row = {
        'SKU Code': "'2320617", 'SKU Name': 'WN PAC 60ML SILVER',
        'Entity': 'PICKLIST', 'Entity Type': 'MANUAL', 'Entity Code': 'PK385',
        'Entity Status': 'COMPLETE', 'From Facility': 'PPETPL Bhiwandi',
        'To Facility': '-', 'Units': '12.0000',
        'Inventory Updated At': '2026-03-20 14:30:00',
        'Putaway Codes': '-', 'Transaction Type': 'OUT', 'Sale Order Code': 'SO01234',
    }
    parsed = parse_ledger_row(row)
    assert parsed is not None
    assert parsed['sku_code'] == '2320617'
    assert parsed['stock_change'] == -12.0
    assert parsed['txn_type'] == 'OUT'
    assert parsed['entity'] == 'PICKLIST'
    assert parsed['is_demand'] is True
    assert parsed['facility'] == 'ppetpl'

def test_grn_in():
    row = {
        'SKU Code': "'6312", 'SKU Name': 'Eraser',
        'Entity': 'GRN', 'Entity Type': 'PUTAWAY_GRN_ITEM', 'Entity Code': 'G0719',
        'Entity Status': 'COMPLETE', 'From Facility': '-',
        'To Facility': 'PPETPL Bhiwandi', 'Units': '100.0000',
        'Inventory Updated At': '2026-03-24 15:31:28',
        'Putaway Codes': 'PT1392', 'Transaction Type': 'IN', 'Sale Order Code': '-',
    }
    parsed = parse_ledger_row(row)
    assert parsed['stock_change'] == 100.0
    assert parsed['txn_type'] == 'IN'
    assert parsed['is_demand'] is False

def test_inventory_adjustment_remove():
    row = {
        'SKU Code': "'138", 'SKU Name': 'Eraser',
        'Entity': 'INVENTORY_ADJUSTMENT', 'Entity Type': 'REMOVE', 'Entity Code': '-',
        'Entity Status': '-', 'From Facility': '-',
        'To Facility': 'Art Lounge Bhiwandi', 'Units': '-50.0000',
        'Inventory Updated At': '2026-03-24',
        'Putaway Codes': '-', 'Transaction Type': 'IN', 'Sale Order Code': '-',
    }
    parsed = parse_ledger_row(row)
    assert parsed['stock_change'] == -50.0
    assert parsed['txn_type'] == 'IN'
    assert parsed['facility'] == 'ALIBHIWANDI'

def test_invoices_excluded():
    assert is_excluded_entity('INVOICES') is True
    assert is_excluded_entity('PICKLIST') is False
    assert is_excluded_entity('GRN') is False

def test_empty_sku_returns_none():
    row = {
        'SKU Code': '', 'SKU Name': '', 'Entity': 'PICKLIST',
        'Entity Type': 'MANUAL', 'Entity Code': 'PK1', 'Entity Status': 'COMPLETE',
        'From Facility': 'PPETPL Bhiwandi', 'To Facility': '-', 'Units': '1',
        'Inventory Updated At': '2026-03-20', 'Putaway Codes': '-',
        'Transaction Type': 'OUT', 'Sale Order Code': '-',
    }
    assert parse_ledger_row(row) is None

def test_putaway_cir_is_not_demand():
    row = {
        'SKU Code': "'100", 'SKU Name': 'Item',
        'Entity': 'PUTAWAY_CIR', 'Entity Type': 'PUTAWAY_RECEIVED_RETURNS',
        'Entity Code': 'RP0029', 'Entity Status': 'COMPLETE',
        'From Facility': '-', 'To Facility': 'PPETPL Bhiwandi',
        'Units': '5.0000', 'Inventory Updated At': '2026-03-20',
        'Putaway Codes': '-', 'Transaction Type': 'IN', 'Sale Order Code': '-',
    }
    parsed = parse_ledger_row(row)
    assert parsed['is_demand'] is False
    assert parsed['stock_change'] == 5.0

def test_classify_channel_with_rules():
    rules = [
        {'rule_type': 'entity', 'match_value': 'GRN', 'channel': 'supplier', 'priority': 100, 'is_active': True},
        {'rule_type': 'sale_order_prefix', 'match_value': 'MA-', 'channel': 'online', 'priority': 70, 'is_active': True, 'facility_filter': None},
        {'rule_type': 'sale_order_prefix', 'match_value': 'SO', 'channel': 'store', 'priority': 60, 'is_active': True, 'facility_filter': 'PPETPLKALAGHODA'},
        {'rule_type': 'sale_order_prefix', 'match_value': 'SO', 'channel': 'wholesale', 'priority': 50, 'is_active': True, 'facility_filter': 'ppetpl'},
        {'rule_type': 'default', 'match_value': 'PICKLIST', 'channel': 'wholesale', 'priority': 0, 'is_active': True},
    ]
    # GRN -> supplier
    assert classify_channel({'entity': 'GRN', 'sale_order_code': None, 'facility': 'ppetpl'}, rules) == 'supplier'
    # PICKLIST with MA- order -> online
    assert classify_channel({'entity': 'PICKLIST', 'sale_order_code': 'MA-000123', 'facility': 'ppetpl'}, rules) == 'online'
    # PICKLIST with SO order at Kala Ghoda -> store
    assert classify_channel({'entity': 'PICKLIST', 'sale_order_code': 'SO01234', 'facility': 'PPETPLKALAGHODA'}, rules) == 'store'
    # PICKLIST with SO order at Bhiwandi -> wholesale
    assert classify_channel({'entity': 'PICKLIST', 'sale_order_code': 'SO01234', 'facility': 'ppetpl'}, rules) == 'wholesale'
    # PICKLIST with no order -> default wholesale
    assert classify_channel({'entity': 'PICKLIST', 'sale_order_code': None, 'facility': 'ppetpl'}, rules) == 'wholesale'

def test_classify_channel_fallback():
    # No rules -> hardcoded fallback
    assert classify_channel({'entity': 'GRN', 'sale_order_code': None, 'facility': 'ppetpl'}) == 'supplier'
    assert classify_channel({'entity': 'PUTAWAY_CIR', 'sale_order_code': None, 'facility': 'ppetpl'}) == 'online'
    assert classify_channel({'entity': 'INVENTORY_ADJUSTMENT', 'sale_order_code': None, 'facility': 'ppetpl'}) == 'internal'

if __name__ == "__main__":
    test_picklist_out()
    test_grn_in()
    test_inventory_adjustment_remove()
    test_invoices_excluded()
    test_empty_sku_returns_none()
    test_putaway_cir_is_not_demand()
    test_classify_channel_with_rules()
    test_classify_channel_fallback()
    print("ALL PASS")
