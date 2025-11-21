# Estate Sale Ninja

Automation toolkit for estate sale route planning. Converts manually-collected estate sale data into Google Maps format (KML) with validation tools.

## Tech Stack

- **Python 3.6+** (standard library only, no external dependencies)
- **Data formats**: CSV, KML 2.2, Markdown

## Quick Commands

```bash
# Basic CSV to KML conversion
python3 scripts/csv_to_kml.py <csv> <markdown> [output.kml]

# Enhanced KML with folders, color-coding, filtering
python3 scripts/csv_to_kml_enhanced.py <csv> <markdown> [output.kml]

# Validate KML against source data
python3 scripts/verify_kml.py <csv> <markdown> <kml>

# Verify URLs against live websites (~1.5 min for 50 sales)
python3 scripts/verify_urls.py <kml> [delay_seconds]

# Fix CSV with unquoted commas in Description field
python3 scripts/fix_csv_properly.py <input.csv> [output.csv]
```

## Project Structure

```
scripts/           Python automation tools
examples/          Complete example datasets with source files
.claude/           Detailed instructions and domain knowledge
```

## Code Conventions

- Type hints on all functions (`Dict[str, str]`, `Path`, etc.)
- Docstrings with Args/Returns (reStructuredText style)
- CLI scripts validate input files and exit with code 1 on error
- Address normalization: lowercase, remove extra spaces and commas
- KML descriptions use CDATA sections for HTML content

## Key Patterns

- **Address matching** is the most reliable way to correlate data across files
- **ZIP code searches** on EstateSales.NET yield 400% more results than city searches
- **Description field** format: `"Sat 10am-4pm, Sun 11am-4pm | Parking notes"` (pipe separates hours from notes)

## Verification Criteria

- 100% count match (CSV rows = KML placemarks)
- 90%+ URL match rate against markdown
- All hours and parking info preserved

## See Also

- `.claude/instructions.md` - Detailed data processing protocol, gotchas, domain knowledge
- `README.md` - Full methodology and future roadmap
- `examples/*/PROCESS_LOG.md` - Real-world search methodology
