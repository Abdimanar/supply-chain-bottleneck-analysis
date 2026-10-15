# Power BI Layout & OTIF DAX Guide

Load `output/fulfilment_enriched.csv` (created by `bottleneck_analysis.py`) as `Fulfilment`. Create a `DimDate` table and relate `DimDate[Date]` to `Fulfilment[order_ts]` (date part).

```DAX
DimDate = CALENDARAUTO ()
```

## Core measures

```DAX
Total Orders = COUNTROWS ( Fulfilment )

On-Time Orders =
CALCULATE ( [Total Orders], Fulfilment[on_time] = TRUE () )

In-Full Orders =
CALCULATE ( [Total Orders], Fulfilment[in_full] = TRUE () )

OTIF Orders =
CALCULATE ( [Total Orders], Fulfilment[on_time] = TRUE (), Fulfilment[in_full] = TRUE () )

On-Time % = DIVIDE ( [On-Time Orders], [Total Orders] )
In-Full % = DIVIDE ( [In-Full Orders], [Total Orders] )
OTIF % = DIVIDE ( [OTIF Orders], [Total Orders] )

OTIF Target = 0.95
OTIF Gap to Target = [OTIF %] - [OTIF Target]
```

## Lead-time and bottleneck measures

```DAX
Avg Lead Time (hrs) = AVERAGE ( Fulfilment[total_hrs] )
P90 Lead Time (hrs) = PERCENTILEX.INC ( Fulfilment, Fulfilment[total_hrs], 0.9 )

Avg Pick (hrs)     = AVERAGE ( Fulfilment[pick_hrs] )
Avg Pack (hrs)     = AVERAGE ( Fulfilment[pack_hrs] )
Avg Dispatch Wait  = AVERAGE ( Fulfilment[dispatch_wait_hrs] )
Avg Transit (hrs)  = AVERAGE ( Fulfilment[transit_hrs] )

-- Share of total time per stage (use for a 100% stacked bar)
Pick Share % = DIVIDE ( [Avg Pick (hrs)], [Avg Lead Time (hrs)] )

-- Late orders: how many hours past promise on average
Avg Days Late =
AVERAGEX (
    FILTER ( Fulfilment, Fulfilment[on_time] = FALSE () ),
    DATEDIFF ( Fulfilment[promised_ts], Fulfilment[delivered_ts], HOUR )
)
```

## Time intelligence

```DAX
OTIF % Prior Month =
CALCULATE ( [OTIF %], DATEADD ( DimDate[Date], -1, MONTH ) )

OTIF MoM Change = [OTIF %] - [OTIF % Prior Month]

OTIF % Rolling 4 Weeks =
CALCULATE ( [OTIF %], DATESINPERIOD ( DimDate[Date], MAX ( DimDate[Date] ), -28, DAY ) )
```

## Page layout

```
+------------------------------------------------------------------+
| Slicers: Date range | Warehouse | Region | Carrier                |
+-----------+-----------+-----------+-----------+------------------+
| OTIF %    | On-Time % | In-Full % | Avg Lead  | P90 Lead Time    |
| (gauge    |           |           | Time      |                  |
|  vs 95%)  |           |           |           |                  |
+-----------+-----------+-----------+-----------+------------------+
| Line: OTIF % by week (+ target)  | 100% stacked bar: stage share  |
|                                  | by warehouse                   |
+----------------------------------+--------------------------------+
| Matrix heatmap: Warehouse x      | Bar: OTIF % by carrier,        |
| Region avg lead time (cond. fmt) | sorted ascending               |
+----------------------------------+--------------------------------+
```

Drill-through page "Late Order Detail": order id, warehouse, carrier, hours late, which stage exceeded norm.

## Tips
- Colour OTIF below target in red via conditional formatting on the gap measure.
- Add a Key Influencers visual with `otif` as the metric to surface drivers automatically.
- Turn the EDA findings into a "Top 3 bottlenecks" text card on the landing page.
