# Oracle

Reference method for the smoke fixture. The generator is `lunri.dataset.generate` with seed `20261118`. The line parser is `lunri.mock_model.dollars_to_cents`, which splits on the decimal point and does not use binary floating point.

## smoke-smoke_plain-000

Text:

```text
SYNTHETIC INVOICE. Not a real invoice, vendor, person, or payment.
Invoice number: smoke_plain-000
Total: 10.24 USD
```

Hand calculation:

- The invoice line matches exactly once, so `invoice_number` is `smoke_plain-000`.
- `10.24` splits into whole `10` and fraction `24`.
- Cents are `10 * 100 + 24 = 1024`.
- The currency token is `USD`.
- The digits `1024` do not appear in the text.

Gold in the JSONL row is `currency=USD`, `invoice_number=smoke_plain-000`, `total_cents=1024`. A prediction that parses as those three values is correct. A prediction that parses as `total_cents=1000` with the same id and currency is syntax-valid and wrong.

The same conversion gives `smoke-smoke_plain-001` as `11.78 EUR = 1178` cents and `smoke-smoke_plain-002` as `13.16 GBP = 1316` cents.

## Wilson interval for 3 of 3

The report prints four decimal places. The unrounded 95% Wilson interval from `lunri.stats.wilson_interval(3, 3)` with `z = 1.96` is low `0.43849391955098227`, point `1.0`, high `1.0`.

Hand steps: `z^2 = 3.8416`, denominator `1 + 3.8416 / 3 = 2.280533333`, center `(1 + 3.8416 / 6) / 2.280533333 = 0.719247`, margin `1.96 * sqrt(3.8416 / 36) / 2.280533333 = 0.280753`. Low is `0.719247 - 0.280753 = 0.438494`. High is capped at `1`.

Quality stays `inconclusive` because 3 attempts are below the predeclared minimum of 30, even though the point accuracy is 1. The displayed smoke interval is `0.4385..1.0000`.

## Held-out mock, independent of the model weights

The line parser only fills a field from one exact `Invoice number:` line and one exact `Total:` line. Held-out `distract` rows have those lines. Held-out `block` and `missing_amount` rows do not, so those items are not correct. That is a property of the parser, not a measurement of Qwen.
