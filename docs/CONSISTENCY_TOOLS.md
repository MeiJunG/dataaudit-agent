# Consistency checks

These three adapters are deployed on the V100 server and registered with the Agent, bringing the live registry to 19 tools. Their real tool calls and displayed answers were checked through the running Gradio API.

## Text format

`check_text_quality(columns=None)` examines up to 20 selected text fields. It separates actual null values, whitespace-only strings, and strings with leading/trailing whitespace. Distinct original strings are grouped by strip + Unicode casefold to find spelling variants; several identical original strings alone do not count as a collision. Variants can be intentional. Nothing is normalized or overwritten.

By default it checks text/object fields; an empty selection or more than 20 fields returns a tool error. Examples are bounded and suppressed for sensitive-looking column names. “Blank text” and “outer whitespace” counts can overlap, so do not add them as distinct issue rows.

## Conditional required fields

`check_required_if(condition_column, equals, required_columns)` validates 1–20 required fields only for rows whose condition value exactly matches the supplied string. Matching is case-sensitive and does not trim condition values. Null, empty, and whitespace-only required values count as missing. A record missing several fields is counted once in `affected_rows` and separately for each missing field.

No condition, mandatory-field policy, or allowed business rule is inferred automatically. Zero and false are values, not missing data. Required values are not exposed.

## Date order

`check_date_order(start_column, end_column, allow_equal=True)` validates ISO-8601 date pairs. Date-only and naive timestamps are treated as UTC; timestamps with an offset are normalized to UTC. Missing dates and invalid-date pairs are counted separately and excluded from comparison. With equality disallowed, equal pairs also violate the rule. Numeric epoch values are not guessed.

This tool checks order of two fields, not whether dates are generally plausible or whether a string is an ambiguous locale date. It returns counts without source dates.

## Synthetic reference data

`examples/consistency_checks.csv` has six synthetic rows:

| Question | Reference result |
|---|---|
| Text variants in status | 1 outer-whitespace value; 1 normalization-collision group involving 5 rows |
| Exact status=completed requires amount and recorded_amount | 3 matching rows; 2 affected rows; 1 missing amount and 1 missing recorded_amount |
| order_date <= ship_date | 4 comparable pairs; 1 reversed, 1 equal; 1 invalid pair and 1 missing pair |

The condition intentionally does not match `Completed` or ` completed `. This makes the difference between spelling inspection and exact business-rule application observable.

## Validation boundary

The server passed 25 standard-library checks and 68 dependency-based tests. The 42-task development suite includes six bilingual consistency cases; the baseline passed 42/42 in 62.353 seconds. Separate live web checks exercised all three tool calls and their displayed counts, plus the preview and clearing callbacks. A real CSV upload and full report download were also verified.

These are development fixtures and bounded functional checks. They do not prove arbitrary-data reliability or every model-generated sentence. Subsequent actual browser verification covered the preview, data switching and core interactions; see [visual QA](VISUAL_QA.json).

```bash
python3 -m unittest discover -s checks -v
python -m pytest -q tests
python evaluation/expanded.py --tasks evaluation/nineteen_tasks.json --output results/nineteen.json
python evaluation/check_consistency_web.py --output results/consistency-web.json
```
