# Estate Sale Ninja - Project Instructions

## Data Processing Protocol

### Before Writing Any Code
1. **Inspect actual data structure** - Don't assume format
   ```bash
   head -5 file.csv
   python3 -c "import csv; print(list(csv.DictReader(open('file.csv')))[0])"
   ```
2. **Test parsing immediately** - Verify all fields read correctly
3. **Mock output sample** - Show 1-2 examples, get user approval
4. **Choose simplest matching** - Priority: IDs > addresses > composite keys > fuzzy matching

### Red Flags 🚩
- Match rate < 90% → inspect failures before continuing
- Truncated/missing fields → check CSV quoting/delimiters
- Processing > 100 items → show sample output first

## Web Scraping: EstateSales.NET

### URL Strategy
- ✅ **Use ZIP codes**: `/MI/City/ZIP` (reliable, 400% more results)
- ❌ **Avoid city names**: `/MI/City` (unreliable, 404s, redirects)
- **Search pattern**: Systematic ZIP code iteration
- **URL structure**: City names in URLs not authoritative (JS filtering)

### Data Collection
- **Batching**: 4 WebFetch calls per message for large datasets
- **Expect missing fields**: Not all sales have Directions/Terms/etc.
- **Parse flexibly**: Handle inconsistent data gracefully
- **Deduplicate early**: ZIP codes overlap → track by address/URL

### Context Management
| Dataset Size | Strategy | Token Budget |
|--------------|----------|--------------|
| 1-10 items | Single batch | ~20K |
| 10-50 items | 4 per message | ~2K per item |
| 50+ items | Direct file writes | Avoid displaying |

## Estate Sale Data Patterns

### CSV Structure
- **Description field**: Contains commas (hours, notes separated by "|")
- **Parsing**: May need custom parser if fields aren't quoted
- **Fix command**: `scripts/fix_csv_properly.py` for unquoted comma fields
- **Format**: `"Sat 10am-4pm, Sun 11am-4pm | Parking notes"`

### Matching Strategy
- ✅ **Use addresses** for matching across files (most reliable)
- ❌ **Avoid fuzzy name matching** (sale names vary significantly)
- **Deduplication**: Same address = same sale (even if ZIP codes differ)

### KML Output Format
```xml
<description><![CDATA[
  <h3><a href="URL">Sale Name</a></h3>
  <p><strong>Hours:</strong> All days and times</p>
  <p><strong>Notes:</strong> Parking/special instructions</p>
]]></description>
```
- Title is hyperlinked (no separate "View" link)
- Address in `<address>` tag (not in description)
- Split hours from notes on "|" separator

## Verification Tools

### Quick Checks
```bash
# Test CSV parsing
python3 scripts/test_csv_read.py

# Verify KML accuracy
python3 scripts/verify_kml.py input.csv details.md output.kml

# Validate against live websites (slow, ~1.5 min for 50 sales)
python3 scripts/verify_urls.py output.kml
```

### Success Criteria
- 100% count match (CSV → KML)
- 100% address accuracy
- 90%+ URL match rate
- All time/parking info preserved

## Common Gotchas

| Issue | Cause | Solution |
|-------|-------|----------|
| Truncated times | Unquoted CSV commas | Run `fix_csv_properly.py` |
| Low URL matches | Using name matching | Match by address instead |
| Missing parking notes | Not splitting on "\|" | Parse description properly |
| City search finds 0 sales | Using city URLs | Use ZIP code URLs instead |
| Duplicate sales | ZIP code overlap | Deduplicate by address |
| Context overflow | Displaying all data | Write directly to files |

## Development Workflow

1. **Discovery** (inspect data, identify keys)
2. **Parse validation** (test with 3 samples)
3. **Mock approval** (show output format)
4. **Implementation** (build converter/scraper)
5. **Verification** (run validation tools)

## Domain Knowledge

### EstateSales.NET Patterns
- Most sales are multi-day (96%)
- Common discount: 50% OFF final day (Saturday)
- Payment: Cash/Venmo/Zelle/CashApp increasingly common
- Liability: Nearly all have "enter at own risk" disclaimers
- Large items: Buyers provide own help/transportation
- Entry: Street number system (numbered tickets, first-come)

### Detroit Metro Area
- 30-mile radius = 50+ municipalities
- Premium areas: Bloomfield Hills, Birmingham, Grosse Pointe
- High concentration in affluent suburbs
- Typical hours: 10am-4pm (earliest: 8am, latest close: 5pm)

## Project Files

- `scripts/csv_to_kml.py` - CSV → KML converter with URL hyperlinks
- `scripts/verify_kml.py` - Validate KML against source data
- `scripts/verify_urls.py` - Check data against live websites
- `scripts/fix_csv_properly.py` - Fix unquoted CSV fields
- `examples/*/PROCESS_LOG.md` - Detailed methodology documentation
