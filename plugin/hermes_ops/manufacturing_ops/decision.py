from __future__ import annotations

def build_options(s: dict, policy_version: int) -> list[dict]:
    total = s['replacement_units'] + s['sales_units']
    shortage = max(0, total - s['stock_units'])
    replacement_finish = s['replacement_units'] * s['hours_per_unit']
    initial_sales = max(0, min(s['sales_units'], s['stock_units'] - s['replacement_units']))
    initial_finish = replacement_finish + initial_sales * s['hours_per_unit']
    remaining = s['sales_units'] - initial_sales
    rows = [dict(id='wait', label='Wait for original supply', supplier_id=None, approved=True, receipt=s['original_receipt_hour'], incremental_cost_minor=0, purchase_value_minor=0)]
    rows += [dict(id=p['plan_id'], label=p['label'], supplier_id=p['id'], approved=p['approved'], receipt=p['lead_hours'] + (p['cutoff_delay_hours'] if policy_version >= 2 else 0), incremental_cost_minor=p['incremental_cost_minor'], purchase_value_minor=shortage*s['component_cost_minor']) for p in s['suppliers']]
    out = []
    for r in rows:
        sales_finish = max(initial_finish, r['receipt']) + remaining * s['hours_per_unit'] if remaining else initial_finish
        reasons = []
        if s['stock_units'] < s['replacement_units']:
            reasons.append('Insufficient usable stock for the warranty commitment')
        if not r['approved']:
            reasons.append('Supplier is not approved')
        if r['incremental_cost_minor'] > s['expedite_limit_minor']:
            reasons.append('Incremental spend exceeds delegated authority')
        if replacement_finish > s['replacement_due_hour']:
            reasons.append('Warranty shipment misses its commitment')
        if sales_finish > s['sales_due_hour']:
            reasons.append('Sales shipment misses its commitment')
        out.append(dict(id=r['id'], label=r['label'], supplier_id=r['supplier_id'], feasible=not reasons, reasons=reasons, incremental_cost_minor=r['incremental_cost_minor'], purchase_value_minor=r['purchase_value_minor'], predicted_receipt_hour=r['receipt'], predicted_replacement_ship_hour=replacement_finish, predicted_sales_ship_hour=sales_finish, inventory_after_original_receipt_units=s['stock_units']+s['original_po_units']+(shortage if r['id']!='wait' else 0)-total))
    return sorted(out, key=lambda r: (not r['feasible'], r['incremental_cost_minor'], r['id']))
