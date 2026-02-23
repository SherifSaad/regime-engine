#!/bin/bash
# Save as e.g. audit_frozen.sh, then chmod +x audit_frozen.sh && ./audit_frozen.sh > audit_report.txt

echo "Frozen DB Audit Report - $(date)"
echo "================================="
echo ""

find "/Users/sherifsaad/Documents/regime-engine/data/assets" -name "frozen_*.db" -type f | sort | while read db; do
  symbol=$(basename "$(dirname "$db")")
  frozen_date=$(basename "$db" | sed 's/frozen_//; s/\.db//')
  
  echo "=== $symbol - $frozen_date ==="
  echo "DB path: $db"
  
  # Total bars and esc + diff
  total_bars=$(sqlite3 "$db" "SELECT COUNT(*) FROM bars WHERE symbol='$symbol';" 2>/dev/null || echo "ERROR")
  total_esc=$(sqlite3 "$db" "SELECT COUNT(*) FROM escalation_history_v3 WHERE symbol='$symbol';" 2>/dev/null || echo "ERROR")
  diff=$((total_bars - total_esc))
  echo "Total bars: $total_bars"
  echo "Total esc:  $total_esc"
  echo "Diff (bars - esc): $diff"
  
  # latest_state count (should be 5 if all TFs done)
  latest_n=$(sqlite3 "$db" "SELECT COUNT(*) FROM latest_state WHERE symbol='$symbol';" 2>/dev/null || echo "ERROR")
  echo "latest_state rows: $latest_n"
  
  # Breakdowns only if tables exist
  echo "Timeframe breakdowns:"
  sqlite3 "$db" <<EOF 2>/dev/null || echo "  (query failed - tables missing?)"
.separator " | "
.header on
.mode column
SELECT 'bars' AS tbl, timeframe, COUNT(*) AS n
FROM bars
WHERE symbol='$symbol'
GROUP BY timeframe
UNION ALL
SELECT 'esc' AS tbl, timeframe, COUNT(*) AS n
FROM escalation_history_v3
WHERE symbol='$symbol'
GROUP BY timeframe
UNION ALL
SELECT 'latest' AS tbl, timeframe, COUNT(*) AS n
FROM latest_state
WHERE symbol='$symbol'
GROUP BY timeframe
ORDER BY tbl, timeframe;
EOF
  
  # Quick range check (bars min/max ts)
  echo "Bars date range:"
  sqlite3 "$db" <<EOF 2>/dev/null
SELECT timeframe, MIN(datetime), MAX(datetime) 
FROM bars 
WHERE symbol='$symbol' 
GROUP BY timeframe;
EOF
  
  # Esc asof range
  echo "Esc asof range:"
  sqlite3 "$db" <<EOF 2>/dev/null
SELECT timeframe, MIN(asof), MAX(asof) 
FROM escalation_history_v3 
WHERE symbol='$symbol' 
GROUP BY timeframe;
EOF
  
  # Simple status guess
  if [ "$latest_n" = "5" ] && [ "$diff" -ge 100 ] && [ "$diff" -le 300 ]; then
    echo "STATUS: COMPLETE (looks good, diff in expected range)"
  elif [ "$latest_n" -gt 0 ] && [ "$latest_n" -lt 5 ]; then
    echo "STATUS: PARTIAL (some TFs computed, latest_state=$latest_n/5)"
  else
    echo "STATUS: INCOMPLETE or ERROR (check tables/queries)"
  fi
  
  echo ""
  echo "------------------------------------------"
  echo ""
done
