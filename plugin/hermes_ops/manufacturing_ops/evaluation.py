from __future__ import annotations

def compare_outcome(snapshot: dict, prediction: dict, observed: dict) -> dict:
    required = ('receipt_hour', 'replacement_ship_hour', 'sales_ship_hour')
    missing = [key for key in required if key not in observed]
    if missing:
        return {'complete': False, 'missing': missing}
    actual_sales = observed['sales_ship_hour']
    return {
        'complete': True,
        'synthetic': True,
        'predicted_receipt_hour': prediction['predicted_receipt_hour'],
        'actual_receipt_hour': observed['receipt_hour'],
        'receipt_error_hours': observed['receipt_hour']-prediction['predicted_receipt_hour'],
        'predicted_sales_ship_hour': prediction['predicted_sales_ship_hour'],
        'actual_sales_ship_hour': actual_sales,
        'sales_forecast_error_hours': actual_sales-prediction['predicted_sales_ship_hour'],
        'sales_late_hours': max(0,actual_sales-snapshot['sales_due_hour']),
        'replacement_on_time': observed['replacement_ship_hour'] <= snapshot['replacement_due_hour'],
        'sales_on_time': actual_sales <= snapshot['sales_due_hour'],
        'incremental_cost_minor': prediction['incremental_cost_minor'],
        'purchase_value_minor': prediction['purchase_value_minor'],
        'inventory_after_original_receipt_units': prediction['inventory_after_original_receipt_units'],
        'inventory_exposure_is_projection': True,
    }
