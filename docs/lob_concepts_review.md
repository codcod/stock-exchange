# Limit Order Book Concepts — Article vs. Codebase Review

Source: [Introduction to Limit Order Books](https://www.machow.ski/posts/2021-07-18-introduction-to-limit-order-books/) (machow.ski, 2021)

**Legend:** ✅ Implemented · ⚠️ Partial · ❌ Missing

---

## 1. Core Data Structures

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Order Book** — two-sided list of resting limit orders | ✅ | `OrderBook` class in `services/matching_engine/engine.py`; one instance per ticker |
| **Order** — side, quantity, limit price, submission time | ✅ | `Order` dataclass in `shared/models/domain.py`; all four fields present |
| **Price Level** — discrete price point grouping multiple orders | ✅ | `PriceLevel` dataclass; holds a `Deque[Order]` for FIFO ordering |
| **Tick Size** — minimum price increment between levels | ❌ | No tick size constraint; orders can be submitted at arbitrary decimal prices. Easy to add: a validator in `RiskEngine._check_price_sanity()` rounding price to nearest tick |

---

## 2. Ordering & Priority

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Price/Time Priority** — best price first, earliest order breaks ties | ✅ | Bids sorted descending, asks ascending; `Deque` preserves arrival order within a level |
| **Best Bid / Best Ask** — top-of-book prices | ✅ | `OrderBook.best_bid()` / `best_ask()` methods; published in `MarketDataUpdate` events |
| **Bid/Ask Spread** (`best_ask − best_bid`) | ❌ | Bid and ask prices are stored in `Quote` but the spread is never calculated or exposed. Trivial to add as a `Quote.spread` property |
| **Mid Price** (`(best_bid + best_ask) / 2`) | ❌ | Not calculated anywhere. Trivial one-liner addition to `Quote` |

---

## 3. Order States

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Passive / Resting Order** — limit price doesn't cross the book; waits | ✅ | `_rest()` in the matching engine inserts unmatched orders into the book |
| **Aggressive Order** — limit price crosses opposite best; triggers immediate match | ✅ | `_match()` is called on every `add_order()`; aggressive orders consume resting liquidity |
| **Unfilled** (rests in book untouched) | ✅ | `OrderStatus.OPEN` |
| **Partially Filled** (some quantity traded, remainder rests) | ✅ | `OrderStatus.PARTIALLY_FILLED`; `remaining_quantity` property tracks the open amount |
| **Filled** (fully executed, removed from book) | ✅ | `OrderStatus.FILLED`; `PriceLevel` pops the order from its deque once quantity reaches zero |

---

## 4. Order Lifecycle Operations

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **New Order submission** | ✅ | Full path: HTTP → `OrderManagementService` → `RiskEngine` → `MatchingEngine` |
| **Cancel Order** — remove by ID, release reserved funds | ✅ | `Exchange.cancel_order()`; reserved cash/shares released in `OrderManagementService._release()` |
| **Amend Order** — modify price or quantity | ❌ | Not supported. Moderate effort: requires removing the existing order from the book (losing queue priority), adjusting reservations, and re-submitting. Exchange convention is cancel-then-replace, which is already composable from existing primitives |

---

## 5. Trade Execution

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Trade / Match / Fill** — execution between two parties | ✅ | `Trade` dataclass created in `_execute_fill()`; `TradeExecuted` event published |
| **Single-level trade** — aggressive order fills entirely from one price level | ✅ | Natural outcome of the matching loop |
| **Multi-level trade** — aggressive order sweeps across several price levels | ✅ | `_match()` iterates price levels until the incoming order is fully filled or no crossing price remains |
| **Remainder** — unmatched portion becomes a new passive order | ✅ | After `_match()`, `_rest()` is called if `remaining_quantity > 0` |
| **Slippage** — difference between expected and actual execution price | ❌ | Not measured. For market orders the actual fill prices are in the `Trade` objects but no slippage figure is computed or returned to the caller. Moderate effort to calculate and include in the fill notification |
| **Volume Weighted Average Price (VWAP)** — `Σ(price × qty) / Σqty` | ❌ | `Order.average_fill_price` field exists but is never populated. Easy fix: accumulate in `_execute_fill()` using `(old_vwap * old_qty + price * fill_qty) / new_qty` |
| **Impact Prices** — projected best bid/ask after removing N shares from the book | ❌ | Not implemented. Moderate effort: a read-only query method on `OrderBook` that walks the book without mutating state |

---

## 6. Liquidity

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Add Liquidity / Making** — passive order resting in book | ✅ | Functionally present (any resting limit order adds liquidity) but not labelled or tracked as a metric |
| **Remove Liquidity / Taking** — aggressive order consuming the book | ✅ | Same as above — functionally correct, no metric emitted |
| **Depth** — distance in price levels from top-of-book | ⚠️ | `depth_snapshot()` returns up to 5 levels; the article describes exchanges typically providing 10–25 L2 levels. The cap is arbitrary and easy to increase |
| **Thin Book / Price Impact** — large orders move the market price | ❌ | No detection or warning when the book is thin. Moderate effort to add a liquidity check in the risk engine |
| **Maker/Taker Fees** — different fees for adding vs. removing liquidity | ❌ | No fee model at all. Moderate effort to add a `FeeEngine` service; requires storing fee rates per instrument/account and applying them in `ClearingService` |
| **Market Maker role** — simultaneous bid/ask to profit from spread | ❌ | No special account type or role. The simulator could be extended to run a market-making strategy, but no infrastructure exists |

---

## 7. Order Types

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Limit Order** — executes at limit price or better | ✅ | `OrderType.LIMIT`; price-constrained matching enforced in `_match()` |
| **Market Order** — executes at any available price | ✅ | `OrderType.MARKET`; `price_ok()` always returns `True` |
| **Stop Order** — dormant until a trigger price is reached, then acts as market/limit | ❌ | Not implemented. Moderate-to-hard effort: requires a separate "stop order book" and a price-monitoring loop that activates orders when `last_price` crosses the stop level |

---

## 8. Time-in-Force (TIF)

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Good Till Cancel (GTC)** — active until filled or cancelled | ⚠️ | Implicit default behaviour (orders never expire), but not modelled as an explicit TIF field |
| **Day** — auto-cancel at session end | ❌ | No session concept or end-of-day sweep. Moderate effort: add a `time_in_force` field to `Order` and a scheduled job that cancels DAY orders |
| **Immediate Or Cancel (IOC)** — cancel unfilled remainder immediately | ❌ | Moderate effort: after `_match()`, if TIF is IOC and `remaining_quantity > 0`, skip `_rest()` and cancel instead |
| **Fill Or Kill (FOK)** — all-or-nothing; reject if full quantity unavailable | ❌ | Moderate effort: simulate the match without mutating state, check if fully filled, then either execute or cancel entirely |
| **Post Only** — cancel if order would be aggressive | ❌ | Easy: before calling `_match()`, check if the order would immediately cross; if so, reject it |

---

## 9. Market Data Levels

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Level 1 (L1)** — best bid/ask price and quantity only | ✅ | `Quote` object; `/market-data/quotes/{ticker}` endpoint |
| **Level 2 (L2)** — aggregated price levels (10–25 deep) | ⚠️ | `depth_snapshot()` returns 5 levels per side. The full book is in memory; increasing the cap to 25 is a one-line change |
| **Level 3 (L3)** — individual order visibility | ❌ | Not exposed. Easy to add as a read-only endpoint iterating `PriceLevel.orders`, but not currently implemented |

---

## 10. Special Order Features

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Hidden Order** — active but invisible in market data | ❌ | Not implemented. Moderate effort: add `hidden: bool` to `Order` and exclude hidden orders from `depth_snapshot()` and L2/L3 feeds |
| **Iceberg Order** — visible display quantity + hidden reserve; refills on depletion, losing queue priority | ❌ | Not implemented. Moderate effort: add `display_qty` and `reserve_qty` to `Order`; when the visible portion is filled, refill from reserve and re-insert at tail of the queue (resetting time priority) |

---

## 11. Market Structure & Sessions

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Continuous Trading** — live matching during normal session | ✅ | The exchange runs in continuous-trading mode at all times |
| **Crossed Book** — best bid ≥ best ask (only valid during auctions) | ⚠️ | Prevented in normal operation (matching fires immediately on any cross). There is no auction mode where a crossed book is temporarily allowed |
| **Auction / Call Auction** — pre-session period; orders accepted, no trades execute; finds uncrossing price | ❌ | Not implemented. Hard effort: requires a separate auction order book, an IEP/IEV calculation (maximise executable volume), and a session state machine |
| **Indicative Equilibrium Price (IEP)** | ❌ | Depends on auction (above) |
| **Indicative Equilibrium Volume (IEV)** | ❌ | Depends on auction (above) |
| **Open Price / Close Price** | ❌ | Not tracked. `MarketDataService` stores `last_price` only. Easy to add `open_price` and `close_price` fields to `Quote` |

---

## 12. Constraint Parameters

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Lot Size** — minimum quantity multiple | ✅ | `Instrument.lot_size`; checked in `RiskEngine._check_instrument()` |
| **Tick Size** — minimum price increment | ❌ | (repeated from §1 for completeness) No price rounding or tick-size enforcement |

---

## 13. Other Trading Concepts

| Concept | Status | Notes / Implementation Gap |
|---|---|---|
| **Volume** — total shares traded in a period | ⚠️ | `Quote.volume_today` accumulates per `TradeExecuted` event but resets on restart (not persisted) |
| **Basis Points** — spread or fee unit (1 bps = 0.01%) | ❌ | No fee or spread metric expressed in bps |
| **Price Discovery** — mechanism by which the market price is determined | ✅ | Emergent from the matching engine; `last_price` updated on every trade |
| **"Hit the Bid" / "Lift the Ask"** — directional aggressive order terminology | ⚠️ | The mechanics are correct but the terminology is not surfaced (e.g. no `aggressor_side` field on `Trade`) |

---

## Summary

| Category | Implemented | Partial | Missing |
|---|---|---|---|
| Core data structures | 3 | 0 | 1 (tick size) |
| Ordering & priority | 2 | 0 | 2 (spread, mid price) |
| Order states | 5 | 0 | 0 |
| Order lifecycle | 2 | 0 | 1 (amend) |
| Trade execution | 4 | 0 | 3 (slippage, VWAP, impact) |
| Liquidity | 2 | 1 (depth) | 3 (thin-book, fees, MM) |
| Order types | 2 | 0 | 1 (stop) |
| Time-in-Force | 0 | 1 (GTC implicit) | 4 (DAY, IOC, FOK, Post-Only) |
| Market data levels | 1 | 1 (L2) | 1 (L3) |
| Special order features | 0 | 0 | 2 (hidden, iceberg) |
| Market sessions | 1 | 1 (crossed book) | 4 (auction, IEP, IEV, open/close) |
| Constraints | 1 | 0 | 1 (tick size) |
| Other | 1 | 2 | 1 |
| **Total** | **24** | **6** | **23** |

### Effort classification for missing items

| Effort | Items |
|---|---|
| **Easy** (< 1 day) | Spread & mid-price on `Quote`, VWAP fill on `Order`, open/close price on `Quote`, Post-Only TIF, L3 endpoint, depth cap increase |
| **Moderate** (1–3 days) | Tick size, IOC/FOK TIF, Day TIF + session sweep, slippage reporting, impact price query, amend order, hidden orders, iceberg orders, thin-book risk check, fee engine |
| **Hard** (> 3 days) | Stop/stop-limit orders, call auction + IEP/IEV, full maker/taker fee model, market maker role/rebates |
