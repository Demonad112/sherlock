#!/bin/bash
# Sherlock Advanced Search Script
# Searches for "Colton Darby" across social networks
# Location context: Calgary

set -e

echo "🔍 Sherlock Advanced Search"
echo "============================"
echo "Target: Colton Darby"
echo "Location: Calgary"
echo ""

# Step 1: Install/Verify
echo "📦 Step 1: Ensuring Sherlock is installed..."
python3 copilot_task.py verify > /dev/null 2>&1 || python3 copilot_task.py install
echo "✅ Sherlock ready"
echo ""

# Step 2: Search for variations of the name
echo "🔎 Step 2: Searching for name variations..."
echo ""

# Create results directory
mkdir -p search_results

# Array of search variations
declare -a SEARCH_TERMS=(
    "colton.darby"
    "coltondarby"
    "colton_darby"
    "cdab"
    "ColtonDarby"
    "colton darby"
)

echo "Searching ${#SEARCH_TERMS[@]} username variations..."
echo ""

# Loop through each search term
for i in "${!SEARCH_TERMS[@]}"; do
    term="${SEARCH_TERMS[$i]}"
    index=$((i + 1))
    echo "[$index/${#SEARCH_TERMS[@]}] Searching: $term"
    
    # Run search with CSV output
    python3 copilot_task.py search "$term" --csv > /dev/null 2>&1 || true
    
    # Move results to organized folder
    if [ -f "${term}.csv" ]; then
        mv "${term}.csv" "search_results/${term}_results.csv"
        echo "    ✅ Results saved to search_results/${term}_results.csv"
    fi
done

echo ""
echo "-----------------------------------"
echo ""

# Step 3: Consolidate and analyze results
echo "📊 Step 3: Consolidating results..."
echo ""

# Create consolidated report
cat > search_results/CONSOLIDATION_REPORT.txt << 'EOF'
COLTON DARBY - CONSOLIDATED SEARCH REPORT
==========================================
Location Context: Calgary
Search Date: $(date)

Search Terms Used:
- colton.darby
- coltondarby
- colton_darby
- cdab
- ColtonDarby
- colton darby

Results Summary:
EOF

# Count and aggregate found accounts
total_found=0
declare -A found_sites

for csv_file in search_results/*_results.csv; do
    if [ -f "$csv_file" ]; then
        # Extract found accounts (where exists = CLAIMED)
        grep "CLAIMED" "$csv_file" | cut -d',' -f3 | while read site; do
            echo "  - Found on: $site (from $(basename $csv_file))"
            ((total_found++)) || true
        done
    fi
done

echo ""
echo "Total Found Accounts: $total_found"
echo ""

# Step 4: Display findings
echo "📋 Step 4: Detailed Findings"
echo ""

if ls search_results/*_results.csv 1> /dev/null 2>&1; then
    echo "CSV Results Generated:"
    ls -lh search_results/*_results.csv | awk '{print "  - " $9 " (" $5 ")"}'
    echo ""
    echo "📄 Sample results from first search:"
    head -n 5 search_results/*.csv 2>/dev/null | head -n 10
else
    echo "ℹ️  No results found across variations"
fi

echo ""
echo "-----------------------------------"
echo ""

# Step 5: Summary and recommendations
echo "✅ Search Complete!"
echo ""
echo "📍 Location Context: Calgary"
echo "👤 Name: Colton Darby"
echo ""
echo "Results Location: search_results/"
echo ""
echo "📝 Recommendations for Investigation:"
echo "  1. Review search_results/ directory for detailed CSV files"
echo "  2. Cross-reference found accounts with personal information"
echo "  3. For unconfirmed matches, manually verify account ownership"
echo "  4. Check profile details and activity for location indicators"
echo ""
echo "🔗 Next Steps:"
echo "  • Run with --verbose flag for more details: python3 copilot_task.py search coltondarby --verbose"
echo "  • Search specific sites: python3 copilot_task.py search coltondarby --sites GitHub LinkedIn Twitter"
echo "  • Use --browse to open found profiles in browser: sherlock coltondarby --browse"
echo ""
