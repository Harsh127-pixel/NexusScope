#!/usr/bin/env python3
"""
S3 Leak Hunting — Quick Test Script

This script demonstrates the S3 hunting module functionality without needing
to run the full FastAPI server. It tests the core functions in isolation.

USAGE:
    python examples/test_s3_hunter.py [domain]

EXAMPLES:
    python examples/test_s3_hunter.py example.com
    python examples/test_s3_hunter.py google.com
    python examples/test_s3_hunter.py
"""

import asyncio
import sys
import os

# Add backend directory to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.modules.s3_hunter import (
    _extract_domain_basename,
    _generate_bucket_permutations,
    hunt_s3_buckets,
)


async def test_domain_extraction():
    """Test domain name extraction."""
    print("\n" + "=" * 70)
    print("TEST 1: Domain Name Extraction")
    print("=" * 70)
    
    test_cases = [
        "example.com",
        "https://www.example.com/path",
        "subdomain.example.co.uk",
        "my-startup.io",
        "https://api.github.com",
    ]
    
    for domain in test_cases:
        base = _extract_domain_basename(domain)
        print(f"  {domain:40s} → {base}")


def test_bucket_generation():
    """Test bucket name permutation generation."""
    print("\n" + "=" * 70)
    print("TEST 2: Bucket Name Generation")
    print("=" * 70)
    
    base = "example"
    buckets = _generate_bucket_permutations(base)
    
    print(f"\n  Generated {len(buckets)} bucket permutations for '{base}':")
    print(f"\n  First 20:")
    for bucket in buckets[:20]:
        print(f"    • {bucket}")
    
    print(f"\n  Last 10:")
    for bucket in buckets[-10:]:
        print(f"    • {bucket}")


async def test_s3_hunting(domain: str):
    """Test full S3 hunting workflow."""
    print("\n" + "=" * 70)
    print("TEST 3: Full S3 Bucket Hunting")
    print("=" * 70)
    print(f"\n  Target domain: {domain}")
    print(f"  This may take 30-60 seconds...")
    print(f"  (probing ~50 S3 bucket permutations concurrently)\n")
    
    # Run the hunt
    results = await hunt_s3_buckets(domain)
    
    # Display results
    print("\n" + "─" * 70)
    print("RESULTS")
    print("─" * 70)
    print(f"\n  Domain: {results['domain']}")
    print(f"  Base Name: {results['base_name']}")
    print(f"  Total Checked: {results['total_checked']}")
    
    # Open buckets (vulnerable)
    open_count = len(results['buckets_found']['open'])
    if open_count > 0:
        print(f"\n  🔓 OPEN BUCKETS (Vulnerable): {open_count}")
        for bucket in results['buckets_found']['open']:\n            print(f\"      • {bucket['bucket_name']} (HTTP {bucket['http_code']})\")\n    else:\n        print(f\"\\n  ✓ OPEN BUCKETS: None found (good!)\")\n    \n    # Closed buckets (protected)\n    closed_count = len(results['buckets_found']['closed'])\n    if closed_count > 0:\n        print(f\"\\n  ✓ CLOSED BUCKETS (Protected): {closed_count}\")\n        if closed_count <= 10:\n            for bucket in results['buckets_found']['closed']:\n                print(f\"      • {bucket['bucket_name']} (HTTP {bucket['http_code']})\")\n        else:\n            for bucket in results['buckets_found']['closed'][:5]:\n                print(f\"      • {bucket['bucket_name']} (HTTP {bucket['http_code']})\")\n            print(f\"      ... and {closed_count - 5} more\")\n    \n    # Errors\n    if results['errors']:\n        print(f\"\\n  ⚠ ERRORS:\")\n        for error_type, buckets in results['errors'].items():\n            if buckets:\n                print(f\"      • {error_type.upper()}: {len(buckets)} bucket(s)\")\n    \n    print(\"\\n\" + \"─\" * 70)\n\n\nasync def main():\n    \"\"\"Main test runner.\"\"\"\n    print(\"\\n\" + \"#\" * 70)\n    print(\"#  S3 Leak Hunting Module — Test Suite\")\n    print(\"#\" * 70)\n    \n    # Test 1: Domain extraction\n    await test_domain_extraction()\n    \n    # Test 2: Bucket name generation\n    test_bucket_generation()\n    \n    # Test 3: Full hunt (if domain provided)\n    if len(sys.argv) > 1:\n        domain = sys.argv[1]\n        await test_s3_hunting(domain)\n    else:\n        print(\"\\n\" + \"\" * 70)\n        print(\"TEST 3: Full S3 Bucket Hunting\")\n        print(\"\" * 70)\n        print(\"\\n  Skipped (no domain provided)\")\n        print(\"\\n  To run the full hunt, provide a domain:\")\n        print(\"    python test_s3_hunter.py example.com\")\n    \n    print(\"\\n\" + \"#\" * 70)\n    print(\"#  Test suite complete!\")\n    print(\"#\" * 70 + \"\\n\")\n\n\nif __name__ == \"__main__\":\n    asyncio.run(main())\n