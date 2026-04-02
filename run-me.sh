#!/bin/bash
# COWORK-RELIEF dispatch — run this in your Mac terminal
echo "=== Searching for secrets repo ==="
gh repo list Rphants --json name,url,isPrivate --limit 50

echo ""
echo "=== Searching specifically for 'secret' ==="
gh repo list Rphants --json name,url,isPrivate --limit 50 | grep -i secret

echo ""
echo "=== Done ==="
