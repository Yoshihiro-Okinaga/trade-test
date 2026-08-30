# Parameter Plateau Research — IS Step

## Dataset

- full ranking rows: 64,714
- target/ref pairs: 930
- center eligibility: trade_count >= 150
- neighbor observation floor: trade_count >= 30

## Important rule

min_trade_count=30 is used only to observe weak neighbors.
The center strategy is still selected from rows with trade_count>=150.
This keeps the historical best-t selection rule comparable.

## Local neighborhood

Same target/ref/signal/counter/hold/start.
Only immediate adjacent SMA and threshold settings are treated as local neighbors.
Missing expected neighbors reduce coverage instead of being silently ignored.

## Existing candidates

- OIL_USD <- COPPER_USD: best_t=2.901, neighbor_mean=1.854, neighbor_worst=1.801, coverage=1.00, signal_support>=1=4/5
- GBP_USD <- EUR_GBP: best_t=3.112, neighbor_mean=1.332, neighbor_worst=1.332, coverage=1.00, signal_support>=1=5/5
- AUD_USD <- EUR_GBP: best_t=3.076, neighbor_mean=2.367, neighbor_worst=2.367, coverage=1.00, signal_support>=1=5/5
- AUD_JPY <- EUR_GBP: best_t=2.715, neighbor_mean=1.696, neighbor_worst=1.206, coverage=1.00, signal_support>=1=5/5
- OIL_USD <- GOLD_USD: best_t=2.977, neighbor_mean=1.271, neighbor_worst=1.271, coverage=1.00, signal_support>=1=2/5
- OIL_USD <- SILVER_USD: best_t=2.386, neighbor_mean=1.461, neighbor_worst=0.864, coverage=1.00, signal_support>=1=2/5
- EUR_JPY <- AUD_NZD: best_t=2.470, neighbor_mean=0.335, neighbor_worst=0.222, coverage=1.00, signal_support>=1=4/5
- GBP_JPY <- AUD_NZD: best_t=2.221, neighbor_mean=0.221, neighbor_worst=-0.642, coverage=1.00, signal_support>=1=4/5

## Next

Run the same task universe on 2016-2020.
Do not reselect the best task there.
Merge the exact 2001-2015 frozen centers into development results,
then compare each IS plateau metric separately with development performance.

2021-2025 is not used to define or tune the plateau metrics.