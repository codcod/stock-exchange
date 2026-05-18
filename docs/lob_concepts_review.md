# Limit Order Book Concepts — Article vs. Codebase Review

Source: [Introduction to Limit Order Books](https://www.machow.ski/posts/2021-07-18-introduction-to-limit-order-books/) (machow.ski, 2021)

**Legend:** ✅ Implemented · ⚠️ Partial · ❌ Missing

---

## 1. Core Data Structures

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Order Book** — A two-sided list of resting limit orders. | ✅ | Implemented as the `OrderBook` class in `services/matching_engine/engine.py`, with one instance per ticker. |
| **Order** — Comprises a side, quantity, limit price, and submission time. | ✅ | Defined as a `dataclass` in `shared/models/domain.py`, containing all four required fields. |
| **Price Level** — A discrete price point that groups multiple orders. | ✅ | Implemented as the `PriceLevel` dataclass, which holds a `Deque[Order]` for First-In, First-Out (FIFO) ordering. |
| **Tick Size** — The minimum price increment between price levels. | ❌ | Not implemented. Orders can be submitted at any decimal price. This could be added by implementing a validator in `RiskEngine._check_price_sanity()` to round the price to the nearest tick. |

---

## 2. Ordering & Priority

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Price/Time Priority** — The best price takes precedence, with ties broken by the earliest submission time. | ✅ | Bids are sorted in descending order and asks in ascending order. A `Deque` is used to maintain the arrival order for orders at the same price level. |
| **Best Bid / Best Ask** — The highest bid and lowest ask prices at the top of the book. | ✅ | Implemented as `OrderBook.best_bid()` and `best_ask()` methods, with the values published in `MarketDataUpdate` events. |
| **Bid/Ask Spread** (`best_ask − best_bid`) | ⚠️ | The backend quote APIs do not calculate or expose the spread, but the TUI computes it from L2 depth data via `DepthSnapshot.spread` in `clients/tui/models.py`. |
| **Mid Price** (`(best_bid + best_ask) / 2`) | ❌ | This value is not calculated. It can be added with a simple one-line implementation in the `Quote` object. |

---

## 3. Order States

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Passive / Resting Order** — A limit order with a price that does not cross the book, causing it to wait for a match. | ✅ | The `_rest()` method in the matching engine inserts unmatched orders into the book. |
| **Aggressive Order** — A limit order with a price that crosses the best opposing offer, triggering an immediate match. | ✅ | The `_match()` method is called on every `add_order()` submission, allowing aggressive orders to consume resting liquidity. |
| **Unfilled** — An order that rests in the book without being executed. | ✅ | `OrderStatus.OPEN` |
| **Partially Filled** — An order where a portion of the quantity has been traded, while the remainder continues to rest in the book. | ✅ | `OrderStatus.PARTIALLY_FILLED`; the `remaining_quantity` property tracks the unfilled amount. |
| **Filled** — An order that has been fully executed and removed from the book. | ✅ | `OrderStatus.FILLED`; the `PriceLevel` removes the order from its deque once the quantity reaches zero. |

---

## 4. Order Lifecycle Operations

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **New Order Submission** | ✅ | The full path is: HTTP → `OrderManagementService` → `RiskEngine` → `MatchingEngine`. |
| **Cancel Order** — Removes an order by its ID and releases any reserved funds. | ⚠️ | The path exists via `OrderManagementService.cancel_order()` → `MatchingEngine.cancel()`, and reservations are released in `OrderManagementService._release()`. However, `OrderBook._remove_resting_order()` only removes the head order at each price level, the OMS does not set `OrderStatus.CANCELLED`, and canceling does not emit a `MarketDataUpdate`. |
| **Amend Order** — Modifies the price or quantity of an existing order. | ❌ | Not supported. This would require removing the existing order from the book (losing time priority), adjusting reservations, and re-submitting. The current convention is to cancel and replace, which can be achieved using existing functionalities. |

---

## 5. Trade Execution

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Trade / Match / Fill** — The execution of a trade between two parties. | ✅ | A `Trade` dataclass is created in `_execute_fill()`, and a `TradeExecuted` event is published. |
| **Single-Level Trade** — An aggressive order that is fully filled from a single price level. | ✅ | This is a natural outcome of the matching loop. |
| **Multi-Level Trade** — An aggressive order that sweeps across multiple price levels. | ✅ | The `_match()` method iterates through price levels until the incoming order is fully filled or no more crossing prices are available. |
| **Remainder** — The unmatched portion of an order that becomes a new passive order. | ✅ | After `_match()` is called, `_rest()` is executed if `remaining_quantity > 0`. |
| **Slippage** — The difference between the expected execution price and the actual execution price. | ❌ | Not measured. For market orders, the actual fill prices are recorded in the `Trade` objects, but no slippage figure is computed or returned to the client. This would require moderate effort to calculate and include in the fill notification. |
| **Volume Weighted Average Price (VWAP)** — `Σ(price × qty) / Σqty` | ✅ | Implemented as `Order.average_fill_price`. The matching engine updates it in `_execute_fill()`, and the OMS recomputes/persists it in `OrderManagementService.on_order_filled()`. |
| **Impact Prices** — The projected best bid and ask prices after removing a certain number of shares from the book. | ❌ | Not implemented. This would require a moderate amount of effort to add a read-only query method to `OrderBook` that can walk the book without modifying its state. |

---

## 6. Liquidity

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Add Liquidity / Making** — A passive order that rests in the book. | ✅ | This is functionally present, as any resting limit order adds liquidity, but it is not explicitly labeled or tracked as a metric. |
| **Remove Liquidity / Taking** — An aggressive order that consumes liquidity from the book. | ✅ | This is functionally correct, but no specific metric is emitted. |
| **Depth** — The distance in price levels from the top of the book. | ✅ | Implemented via `depth_snapshot()` and exposed through the matching engine and gateway depth endpoints. The default depth is 10 levels, and the public APIs allow `1..25` levels, which matches the article's typical L2 range. |
| **Thin Book / Price Impact** — A market condition where large orders can significantly move the market price. | ❌ | There is no detection or warning mechanism for when the book is thin. This would require a moderate amount of effort to add a liquidity check in the risk engine. |
| **Maker/Taker Fees** — Different fees for adding versus removing liquidity. | ❌ | No fee model is implemented. This would require a moderate amount of effort to add a `FeeEngine` service, which would involve storing fee rates per instrument/account and applying them in the `ClearingService`. |
| **Market Maker Role** — A participant that simultaneously places bid and ask orders to profit from the spread. | ❌ | No special account type or role is defined. The simulator could be extended to run a market-making strategy, but the necessary infrastructure does not yet exist. |

---

## 7. Order Types

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Limit Order** — Executes at the specified limit price or better. | ✅ | `OrderType.LIMIT`; price-constrained matching is enforced in the `_match()` method. |
| **Market Order** — Executes immediately at the best available price. | ✅ | `OrderType.MARKET`; the `price_ok()` method always returns `True`. |
| **Stop Order** — Remains dormant until a trigger price is reached, at which point it becomes a market or limit order. | ❌ | Not implemented. This would require a moderate-to-hard effort, including a separate "stop order book" and a price-monitoring loop to activate orders when the `last_price` crosses the stop level. |

---

## 8. Time-in-Force (TIF)

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Good Till Cancel (GTC)** — The order remains active until it is either filled or cancelled. | ⚠️ | This is the implicit default behavior, as orders do not expire, but it is not modeled as an explicit Time-in-Force (TIF) field. |
| **Day** — The order is automatically cancelled at the end of the trading session. | ❌ | There is no concept of a trading session or an end-of-day sweep. This would require a moderate amount of effort to implement, including adding a `time_in_force` field to the `Order` and a scheduled job to cancel DAY orders. |
| **Immediate Or Cancel (IOC)** — The unfilled portion of the order is cancelled immediately after submission. | ❌ | This would require a moderate amount of effort. After `_match()` is called, if the TIF is IOC and `remaining_quantity > 0`, the `_rest()` method would be skipped and the order would be cancelled instead. |
| **Fill Or Kill (FOK)** — The order must be executed in its entirety or not at all; if the full quantity is not available, the order is rejected. | ❌ | This would require a moderate amount of effort. It would involve simulating the match without modifying the state, checking if the order can be fully filled, and then either executing or cancelling it entirely. |
| **Post Only** — The order is cancelled if it would be aggressive (i.e., if it would execute immediately). | ❌ | This would be easy to implement. Before calling `_match()`, a check would be performed to determine if the order would immediately cross the spread; if so, it would be rejected. |

---

## 9. Market Data Levels

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Level 1 (L1)** — Shows only the best bid/ask price and quantity. | ⚠️ | The quote APIs expose best bid/ask prices and last price, but not top-of-book quantities. Best-size quantities are available only indirectly via depth snapshots. |
| **Level 2 (L2)** — Displays aggregated price levels, typically 10–25 levels deep. | ✅ | Implemented via `depth_snapshot()` and the `/market-data/{ticker}/depth` gateway endpoint. Clients can request `1..25` aggregated levels per side. |
| **Level 3 (L3)** — Provides visibility into individual orders. | ❌ | Not exposed. This could be easily added as a read-only endpoint that iterates over `PriceLevel.orders`, but it is not currently implemented. |

---

## 10. Special Order Features

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Hidden Order** — An active order that is not visible in market data. | ❌ | Not implemented. This would require a moderate amount of effort, including adding a `hidden: bool` flag to the `Order` and excluding hidden orders from `depth_snapshot()` and L2/L3 data feeds. |
| **Iceberg Order** — An order with a visible display quantity and a hidden reserve, which refills upon depletion and loses time priority. | ❌ | Not implemented. This would require a moderate amount of effort, including adding `display_qty` and `reserve_qty` to the `Order`. When the visible portion is filled, it would be refilled from the reserve and re-inserted at the tail of the queue, resetting its time priority. |

---

## 11. Market Structure & Sessions

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Continuous Trading** — Live matching that occurs during a normal trading session. | ✅ | The exchange operates in continuous-trading mode at all times. |
| **Crossed Book** — A state where the best bid is greater than or equal to the best ask, which is only valid during auctions. | ⚠️ | This is prevented during normal operation, as the matching engine fires immediately on any cross. There is no auction mode where a crossed book is temporarily allowed. |
| **Auction / Call Auction** — A pre-session period where orders are accepted but no trades are executed, used to determine an uncrossing price. | ❌ | Not implemented. This would be a hard-effort task, requiring a separate auction order book, an Indicative Equilibrium Price (IEP) and Indicative Equilibrium Volume (IEV) calculation, and a session state machine. |
| **Indicative Equilibrium Price (IEP)** | ❌ | Dependent on the implementation of an auction (see above). |
| **Indicative Equilibrium Volume (IEV)** | ❌ | Dependent on the implementation of an auction (see above). |
| **Open Price / Close Price** | ❌ | Not tracked. The `MarketDataService` only stores the `last_price`. It would be easy to add `open_price` and `close_price` fields to the `Quote` object. |

---

## 12. Constraint Parameters

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Lot Size** — The minimum quantity multiple for an order. | ✅ | `Instrument.lot_size`; this is checked in `RiskEngine._check_instrument()`. |
| **Tick Size** — The minimum price increment. | ❌ | (Repeated from §1 for completeness) No price rounding or tick-size enforcement is implemented. |

---

## 13. Other Trading Concepts

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Volume** — The total number of shares traded in a given period. | ⚠️ | `Quote.volume_today` is accumulated with each `TradeExecuted` event but is reset on restart, as it is not persisted. |
| **Basis Points** — A unit used to express the spread or a fee (1 bps = 0.01%). | ❌ | No fee or spread metrics are expressed in basis points. |
| **Price Discovery** — The mechanism by which the market price is determined. | ✅ | This emerges from the matching engine, with the `last_price` being updated on every trade. |
| **"Hit the Bid" / "Lift the Ask"** — Terminology for directional aggressive orders. | ⚠️ | The mechanics are correctly implemented, but the terminology is not explicitly surfaced (e.g., there is no `aggressor_side` field on the `Trade` object). |

---

## Summary

| Category | Implemented | Partial | Missing |
|---|---|---|---|
| Core data structures | 3 | 0 | 1 (tick size) |
| Ordering & priority | 2 | 1 (spread) | 1 (mid price) |
| Order states | 5 | 0 | 0 |
| Order lifecycle | 1 | 1 (cancel) | 1 (amend) |
| Trade execution | 5 | 0 | 2 (slippage, impact) |
| Liquidity | 3 | 0 | 3 (thin-book, fees, MM) |
| Order types | 2 | 0 | 1 (stop) |
| Time-in-Force | 0 | 1 (GTC implicit) | 4 (DAY, IOC, FOK, Post-Only) |
| Market data levels | 1 (L2) | 1 (L1) | 1 (L3) |
| Special order features | 0 | 0 | 2 (hidden, iceberg) |
| Market sessions | 1 | 1 (crossed book) | 4 (auction, IEP, IEV, open/close) |
| Constraints | 1 | 0 | 1 (tick size) |
| Other | 1 | 2 | 1 |
| **Total** | **25** | **7** | **22** |

### Effort classification for remaining gaps

| Effort | Items |
|---|---|
| **Easy** (< 1 day) | Backend spread and mid-price on quote APIs, top-of-book size on L1 quote responses, open/close price on `Quote`, Post-Only TIF, L3 endpoint |
| **Moderate** (1–3 days) | Tick size, IOC/FOK TIF, Day TIF + session sweep, slippage reporting, impact price query, amend order, hidden orders, iceberg orders, thin-book risk check, fee engine, fully correct queued-order cancellation |
| **Hard** (> 3 days) | Stop/stop-limit orders, call auction + IEP/IEV, full maker/taker fee model, market maker role/rebates |
