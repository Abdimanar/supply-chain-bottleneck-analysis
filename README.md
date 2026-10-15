# Operational Efficiency & Supply Chain Bottleneck Analysis

> Exploratory analysis of order-fulfilment logs to uncover where delivery time is lost, with OTIF (On-Time In-Full) tracking ready for Power BI.

## Business problem
Late and incomplete deliveries damage customer trust and increase cost. Management knows OTIF is below target but not **why**: is it picking, packing, waiting for the carrier, or transit?

## What's inside
| File | Purpose |
|---|---|
| `bottleneck_analysis.py` | Cleans logs, engineers stage durations, computes OTIF, produces 5 charts |
| `powerbi_otif_guide.md` | DAX measures and dashboard layout for OTIF tracking |
| `output/` | Enriched dataset + PNG charts |

## Quick start
```bash
pip install pandas numpy matplotlib seaborn
python bottleneck_analysis.py                    # synthetic sample data
python bottleneck_analysis.py --input logs.csv   # your own logs
```

## Method
1. **Clean:** parse timestamps, drop duplicates/missing rows, remove impossible stage sequences.
2. **Engineer:** hours per stage (pick, pack, dispatch wait, transit), total lead time, on-time / in-full / OTIF flags.
3. **Diagnose:** stage share of total time, then segment by warehouse, carrier and region.
4. **Visualise:** stage breakdown, boxplots, heatmaps, carrier OTIF vs target, weekly trend.

## OTIF definition
An order counts as OTIF only if it is **delivered on or before the promised time AND shipped in full** (`qty_shipped >= qty_ordered`). OTIF % = OTIF orders ÷ total orders.

## Findings (synthetic sample, with bottlenecks deliberately seeded)
- OTIF is 84.5% (on-time 90.3%, in-full 93.4%) against a 95% target.
- Transit is the largest block of time (about 64%), but it is mostly set by geography; dispatch wait (about 18%) is the biggest controllable delay.
- Mombasa averages 52.5 hrs order-to-delivery versus about 46 at the other warehouses, driven by slower picking.
- EcoMove averages 55.8 hrs versus about 45 for the other carriers because packed orders wait longer for collection.
- Short shipments cap In-Full % at about 93% regardless of speed, so inventory availability matters as much as logistics.

> Replace with findings from real data or a public dataset once you swap it in.

## Recommendations template
| Bottleneck | Evidence | Action | KPI |
|---|---|---|---|
| Slow picking at warehouse X | Avg pick hrs vs other sites | Re-slot fast movers, add pick wave | Pick hrs |
| Carrier pickup delay | Dispatch wait by carrier | Pickup SLA / reallocate volume | Dispatch wait |
| Short shipments | In-Full % | Safety stock on top SKUs | In-Full % |

## Author
Abdimanar Edin Guyo: Accountant, Financial Analyst & Data Analyst
