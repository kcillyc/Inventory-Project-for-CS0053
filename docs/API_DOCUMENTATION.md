# External API integration

## Provider/purpose

Frankfurter provides reference foreign-exchange data used to convert current PHP inventory value. The public API requires no key and returns reference rates, not trading quotes. See [official documentation](https://frankfurter.dev/), checked 23 November 2026. Availability and terms can change.

| Item | Contract |
| --- | --- |
| Method | GET over HTTPS |
| Base | https://api.frankfurter.dev |
| Endpoint | /v2/rate/php/{target} |
| Target | usd, eur, sgd, jpy, gbp only |
| Headers | Accept: application/json; educational User-Agent |
| Authentication/body | None |
| Expected JSON | Object with base, quote, rate and date |
| Limits | 8-second socket timeout, 65,536-byte response cap; successful quotes cached 900 seconds per target in this process |

Only currency codes are sent. Products, quantities and value totals remain local. Decimal conversion uses ROUND_HALF_UP to two decimals.

## Real integration acceptance

1. Run python app.py --menu --demo --db demo.db.
2. Choose 11, then USD.
3. Observe value, rate, provider and observation date. First success says Live request. Repeat in the same session within 15 minutes to see Cached.
4. Unsupported codes or unavailable network produce an error, after which local inventory remains usable.

Other entry points: python app.py --report --currency USD --db demo.db; docs/requests.http in REST Client. ApplicationConnection is a local Python interface, not a hosted API.

```http
GET https://api.frankfurter.dev/v2/rate/php/usd
Accept: application/json
```

Normalized example corresponding to actual evidence/live-usd.txt (not a raw HTTP capture):

```json
{"base":"PHP","quote":"USD","rate":0.015672,"date":"2026-11-23"}
```

The actual demo contains 25 units at PHP 50.00. PHP 1,250.00 times 0.015672 rounds to USD 19.59. Later requests may differ. Actual EUR/SGD/JPY/GBP calls are saved separately in evidence/live-*.txt.

## Failure behavior

| Condition | Response |
| --- | --- |
| Unsupported target | Reject before HTTP |
| HTTP 429 | Ask operator to wait before retrying |
| Other HTTP failure | Show status and retry-later message |
| Network/TLS/timeout/transport error | Connection message; local inventory unchanged |
| Empty, malformed, oversized or wrong-pair response | Reject provider data |
| Missing/invalid date, boolean/non-numeric/nonfinite/nonpositive rate | Reject provider data |
| Fresh cached success | Label Cached and avoid another request |
| Expired quote or failed request | Do not substitute expired or fictional data |

The socket timeout is not a total wall-clock guarantee. Synchronous requests temporarily occupy the menu. Avoid repeated automated polling, respect service limits/terms and retain provider/date attribution. Offline tests use controlled responses for determinism; live report files prove separate actual network execution.
