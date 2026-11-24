# Local application contract

Construct create_application(database_path), then call connection.execute(action, **fields). ActionResult contains ok, data and error. The UI shows recoverable errors and continues. This is a local Python dispatcher, not an HTTP server.

| Action | Fields | Success data |
| --- | --- | --- |
| view_products | none | active list[Product] |
| add_product | sku, name, category, quantity, price_php, reorder_level | Product |
| prepare_edit | product_id | active Product including version |
| edit_product | product_id, sku, name, category, price_php, reorder_level, expected_version | Product |
| stock_in/stock_out | product_id, quantity, reason | Product with new balance |
| search | query | list[Product] |
| low_stock | none | list[Product] |
| movement_history | limit=200 | newest list[Movement] |
| archive | product_id, confirmed=True | archived Product |
| summary | none | total_products, low_stock_products, total_quantity, total_value_cents |
| currency_report | currency=USD | total_php, converted_total, currency, rate, rate_date, provider, cached |
| export_csv | none | CSV text; UI handles destination |

Terminal integers may be digit strings or valid integer objects. Prices must be decimal text such as 12.50, not float. The service takes integer centavos. Retain the version loaded before edit prompts; refreshing it just before save defeats conflict detection.

```python
from application_connection import create_application

connection = create_application("example.db")
result = connection.execute(
    "add_product", sku="NB001", name="Notebook", category="School Supplies",
    quantity="10", price_php="12.50", reorder_level="3",
)
if result.ok:
    print(result.data.id)
else:
    print(result.error)
```

This writes example.db; use a separate experimental path. Direct repository calls are also validated, but the dispatcher/service provide the full operator-facing contract.
