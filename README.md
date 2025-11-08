# Estate Sale Ninja 🥷

**A comprehensive methodology for finding, organizing, and planning estate sale routes**

Estate Sale Ninja is a systematic approach to discovering and documenting estate sales within a target area, with route optimization and Google Maps integration. This project provides a proven methodology that can be applied to any location and date.

## What This Project Does

Estate Sale Ninja helps you:
- **Find ALL estate sales** in your area using systematic ZIP code-based searches
- **Organize sales geographically** into efficient route clusters
- **Generate Google Maps imports** for visual planning
- **Create detailed documentation** with hours, companies, and tips for each sale
- **Optimize your route** to minimize backtracking and maximize coverage

## How It Works

### The Methodology

1. **Define Your Search Area**
   - Choose a center point (e.g., Bloomfield Hills, MI)
   - Set a radius (e.g., 30 miles)
   - Identify all cities/municipalities within range

2. **Collect ZIP Codes**
   - List all ZIP codes for cities in your target area
   - Include multiple ZIPs for larger cities
   - Cast a wide net (40+ ZIP codes is common for 30-mile radius)

3. **Systematic Search on EstateSales.NET**
   - Use ZIP code-based URL pattern: `/MI/[City]/[ZIP]`
   - ZIP codes are more reliable than city names (see Process Log)
   - Search each ZIP code individually for complete coverage

4. **Gather Detailed Information**
   - Title and hyperlink to listing
   - Hours for each day
   - Full address
   - Hosting company/contact info
   - Directions, terms & conditions, descriptions
   - Payment methods and special notes

5. **Optimize Routes**
   - Group sales into geographic clusters
   - Organize by proximity to minimize travel
   - Consider opening/closing times
   - Create realistic daily itineraries

6. **Generate Outputs**
   - **CSV file** for Google My Maps import
   - **Markdown documentation** with complete details
   - **Quick reference sections** by category (MCM, tools, fashion, etc.)

### Key Discovery: ZIP Codes vs. City Names

Through trial and error, we discovered that **ZIP code-based searches** yield 400% more results than city-based searches. This is because:
- City names in URLs are not authoritative on EstateSales.NET
- The site uses ZIP codes for actual location filtering
- URLs redirect inconsistently based on city names
- ZIP code searches are reliable and comprehensive

See `examples/2025-11-08-bloomfield-hills/PROCESS_LOG.md` for full details.

## Example Output

The `examples/2025-11-08-bloomfield-hills/` folder contains a complete real-world example:

- **Estate_Sales_11-08-2025.csv** - Ready-to-import Google Maps file
- **Estate_Sales_11-08-2025_Details.md** - Comprehensive documentation with route clusters
- **PROCESS_LOG.md** - Detailed methodology and lessons learned

This example found **50 estate sales** within 30 miles of Bloomfield Hills, MI, organized into 12 route clusters.

## Using the Methodology

### Step-by-Step Guide

1. **Prepare Your Search**
   ```
   Center Point: [Your City, State ZIP]
   Radius: [Miles]
   Date Range: [Start Date - End Date]
   ```

2. **Build ZIP Code List**
   - Use Google Maps to identify cities in radius
   - Look up ZIP codes for each city
   - Create a checklist to track searches

3. **Search EstateSales.NET**
   - For each ZIP code, visit: `https://www.estatesales.net/[State]/[City]/[ZIP]`
   - Filter by your target date
   - Record each sale's URL

4. **Collect Details**
   - Visit each sale's individual page
   - Copy key information (hours, address, company, tips)
   - Note special features (50% off days, specialty items, etc.)

5. **Organize Geographically**
   - Group sales by proximity
   - Estimate distances from your center point
   - Create logical clusters for efficient routing

6. **Generate Outputs**
   - Create CSV with format: `Name,Address,City,State,ZIP,Description`
   - Import to Google My Maps for visualization
   - Write detailed documentation with route suggestions

### Tips for Success

- **Time Investment:** Plan for 2-4 hours for comprehensive 30-mile search
- **Coverage:** Expect 30-50+ sales in suburban metro areas
- **Deduplication:** Some sales appear in multiple ZIP searches - track by address
- **Saturday Discounts:** Many sales offer 50% off on final day
- **Early Bird:** Start with closest sales when they open (often 8-10am)

## Outputs Explained

### CSV File (Google Maps Import)

```csv
Name,Address,City,State,ZIP,Description
50% off Saturday JP McCarthy Home,1299 Orchard Ridge Road,Bloomfield Hills,MI,48304,Sat 12pm-3pm | Estate Sales By Beth
```

- **Name:** Includes sale hours and company for quick reference
- **Address:** Full street address for precise mapping
- **Description:** Condensed highlights and key details

**How to Import:**
1. Go to [Google My Maps](https://www.google.com/maps/d/)
2. Create a New Map
3. Click "Import" and upload your CSV
4. All sales will be plotted automatically

### Markdown Documentation

Comprehensive file with:
- **Route Clusters:** Sales organized by geographic area
- **Full Details:** Hours, address, company, contact info
- **Tips Section:** Directions, terms, descriptions, payment methods
- **Quick References:** Sales by category (MCM, tools, fashion, etc.)
- **Discount Highlights:** 50% off sales, special promotions

## Future Roadmap

This project currently documents the **manual methodology**. Future enhancements will include:

### Phase 1: Automation Tools
- [ ] Python/Node scripts to automate ZIP code searches
- [ ] Web scraping for automatic data collection
- [ ] CSV and markdown generation scripts

### Phase 2: Enhanced Features
- [ ] GPS coordinate collection for precise routing
- [ ] Time-based route optimization (opening/closing hours)
- [ ] Category filtering (MCM, tools, fashion, antiques)
- [ ] Google Maps API integration for drive time estimates

### Phase 3: Web Application
- [ ] Interactive web interface
- [ ] User inputs: location, radius, date range
- [ ] Automatic map generation and route planning
- [ ] Mobile-responsive design

### Phase 4: Advanced Features
- [ ] Weekly automated reports
- [ ] Keyword alerts (e.g., "Steinway piano", "Eames chair")
- [ ] Company ratings and reviews
- [ ] Calendar integration with reminders

## Why This Methodology Works

Traditional estate sale searching is inefficient:
- ❌ Browsing city-by-city misses sales due to URL inconsistencies
- ❌ Single-location searches only show nearby sales
- ❌ No route optimization leads to backtracking
- ❌ Manual tracking is error-prone and time-consuming

Estate Sale Ninja methodology:
- ✅ ZIP code-based searches ensure complete coverage
- ✅ Systematic approach finds 400% more sales
- ✅ Geographic clustering minimizes travel time
- ✅ Documentation prevents missed opportunities
- ✅ Repeatable process for any location/date

## Contributing

This is an open methodology. Contributions welcome:
- Additional search techniques
- Automation scripts
- Route optimization algorithms
- Documentation improvements
- Examples from other regions

## License

Licensed under the Apache License 2.0. See LICENSE file for details.

---

**Project Status:** Documentation Phase
**Next Steps:** Build automation tools
**Example Dataset:** November 8, 2025 - Bloomfield Hills, MI (50 sales)
