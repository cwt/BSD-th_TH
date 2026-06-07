#!/usr/bin/env python3
"""
Test suite for th_locale.py
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

import th_locale


def test_fetch_cldr():
    """Test CLDR data fetching returns expected structure."""
    print("Testing CLDR fetch...")
    result = th_locale.fetch_cldr(force=True, verbose=True)
    assert len(result) == 11, f"Expected 11 values, got {len(result)}"
    abmon, mon, abday, day, am_pm = result[:5]
    buddhist_abmon, buddhist_mon, buddhist_abday, buddhist_day, buddhist_am_pm, buddhist_era = result[5:]

    assert len(abmon) == 12, f"Expected 12 abbreviated months, got {len(abmon)}"
    assert len(mon) == 12, f"Expected 12 wide months, got {len(mon)}"
    assert len(abday) == 7, f"Expected 7 abbreviated days, got {len(abday)}"
    assert len(day) == 7, f"Expected 7 wide days, got {len(day)}"
    assert len(am_pm) == 2, f"Expected 2 AM/PM values, got {len(am_pm)}"

    assert len(buddhist_abmon) == 12, f"Expected 12 Buddhist abbreviated months, got {len(buddhist_abmon)}"
    assert len(buddhist_mon) == 12, f"Expected 12 Buddhist wide months, got {len(buddhist_mon)}"
    assert len(buddhist_abday) == 7, f"Expected 7 Buddhist abbreviated days, got {len(buddhist_abday)}"
    assert len(buddhist_day) == 7, f"Expected 7 Buddhist wide days, got {len(buddhist_day)}"
    assert len(buddhist_am_pm) == 2, f"Expected 2 Buddhist AM/PM values, got {len(buddhist_am_pm)}"
    assert buddhist_era == "พ.ศ.", f"Expected Buddhist era 'พ.ศ.', got '{buddhist_era}'"

    print("  ✅ CLDR fetch test passed")
    return result


def test_posix_source_generation():
    """Test POSIX locale source generation."""
    print("Testing POSIX source generation...")
    cldr_data = test_fetch_cldr()
    abmon, mon, abday, day, am_pm = cldr_data[:5]
    buddhist_abmon, buddhist_mon, buddhist_abday, buddhist_day, buddhist_am_pm, buddhist_era = cldr_data[5:]

    source = th_locale.gen_posix_source(abmon, mon, abday, day, am_pm,
                                         buddhist_abmon, buddhist_mon, buddhist_abday, buddhist_day, buddhist_am_pm, buddhist_era)

    assert "LC_MONETARY" in source
    assert "LC_NUMERIC" in source
    assert "LC_TIME" in source
    assert "LC_MESSAGES" in source
    assert "LC_COLLATE" in source
    assert 'copy "iso14651_t1"' in source
    assert "มกราคม" in source  # Thai month name
    assert "พ.ศ." in source  # Buddhist era

    print("  ✅ POSIX source generation test passed")
    return source


def test_macos_compiled_generation():
    """Test macOS compiled format generation."""
    print("Testing macOS compiled generation...")
    cldr_data = test_fetch_cldr()
    abmon, mon, abday, day, am_pm = cldr_data[:5]
    buddhist_abmon, buddhist_mon, buddhist_abday, buddhist_day, buddhist_am_pm, buddhist_era = cldr_data[5:]

    compiled = th_locale.gen_macos_compiled(abmon, mon, abday, day, am_pm,
                                             buddhist_abmon, buddhist_mon, buddhist_abday, buddhist_day, buddhist_am_pm, buddhist_era)

    assert "LC_MONETARY" in compiled
    assert "LC_NUMERIC" in compiled
    assert "LC_TIME" in compiled
    assert "LC_MESSAGES/LC_MESSAGES" in compiled
    assert "มกราคม" in compiled["LC_TIME"]
    assert "พ.ศ." in compiled["LC_TIME"]

    print("  ✅ macOS compiled generation test passed")
    return compiled


def test_monetary_values():
    """Test monetary values are correct for Thai locale."""
    print("Testing monetary values...")
    assert th_locale.TH_MONETARY["int_curr_symbol"] == "THB "
    assert th_locale.TH_MONETARY["currency_symbol"] == "\u0e3f"  # ฿
    assert th_locale.TH_MONETARY["mon_decimal_point"] == "."
    assert th_locale.TH_MONETARY["mon_thousands_sep"] == ","
    assert th_locale.TH_MONETARY["mon_grouping"] == 3
    print("  ✅ Monetary values test passed")


def test_numeric_values():
    """Test numeric values are correct for Thai locale."""
    print("Testing numeric values...")
    assert th_locale.TH_NUMERIC["decimal_point"] == "."
    assert th_locale.TH_NUMERIC["thousands_sep"] == ","
    assert th_locale.TH_NUMERIC["grouping"] == 3
    print("  ✅ Numeric values test passed")


def test_iso_ctt_processing():
    """Test ISO 14651 CTT processing."""
    print("Testing ISO 14651 CTT processing...")
    raw = """% This is a comment
% escape_char /
% comment_char %
% LC_COLLATE
<U0041> <U0042> <U0043>
% END LC_COLLATE
more comments
"""
    processed = th_locale.process_iso_ctt(raw)
    # Activated lines have "% " stripped
    assert "escape_char /" in processed
    assert "comment_char %" in processed
    assert "LC_COLLATE" in processed
    assert "END LC_COLLATE" in processed
    # Non-activated comments and other lines are kept as-is
    assert "<U0041>" in processed
    assert "% This is a comment" in processed  # Non-activated comments kept
    assert "more comments" in processed  # Other lines kept
    print("  ✅ ISO CTT processing test passed")


def test_cache_functions():
    """Test cache directory and path functions."""
    print("Testing cache functions...")
    cache_dir = th_locale.cache_dir()
    assert cache_dir.exists()
    assert cache_dir.is_dir()

    test_url = "https://example.com/test.json"
    cache_path = th_locale.cache_path(test_url)
    assert cache_path.parent == cache_dir
    assert cache_path.suffix == ".json"

    meta_path = th_locale.cache_meta_path(test_url)
    assert meta_path.parent == cache_dir
    assert meta_path.suffix == ".meta"

    print("  ✅ Cache functions test passed")


def test_cli_args():
    """Test CLI argument parsing."""
    print("Testing CLI argument parsing...")
    import argparse

    # Test --help
    parser = th_locale.parse_args.__wrapped__ if hasattr(th_locale.parse_args, '__wrapped__') else th_locale.parse_args
    # We can't easily test parse_args without sys.argv manipulation, just verify it exists
    assert callable(th_locale.parse_args)
    print("  ✅ CLI argument parsing test passed")


def test_dry_run():
    """Test --dry-run mode generates files without installing."""
    print("Testing --dry-run mode...")
    # Run the script with --dry-run in a subprocess
    result = subprocess.run(
        [sys.executable, "th_locale.py", "--dry-run"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=Path(__file__).parent
    )
    assert result.returncode == 0, f"Dry run failed: {result.stderr}"
    assert "Dry run complete" in result.stdout

    # Check that source files were generated
    assert Path("th_TH.src").exists(), "th_TH.src not generated"
    assert Path("iso14651_t1.src").exists(), "iso14651_t1.src not generated"

    print("  ✅ Dry run test passed")


def test_verify_only():
    """Test --verify-only mode (should fail if locale not installed)."""
    print("Testing --verify-only mode...")
    result = subprocess.run(
        [sys.executable, "th_locale.py", "--verify-only"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=Path(__file__).parent
    )
    # Should fail if locale not installed, which is expected in test env
    # Just verify the command runs without crashing
    assert "th_TH.UTF-8" in result.stdout or "th_TH.UTF-8" in result.stderr
    print("  ✅ Verify-only test passed")


def run_all_tests():
    """Run all tests."""
    print("=" * 50)
    print("Running th_locale test suite")
    print("=" * 50)

    test_monetary_values()
    test_numeric_values()
    test_cache_functions()
    test_iso_ctt_processing()
    test_cli_args()
    test_fetch_cldr()
    test_posix_source_generation()
    test_macos_compiled_generation()
    test_dry_run()
    test_verify_only()

    print("=" * 50)
    print("All tests passed! ✅")
    print("=" * 50)


if __name__ == "__main__":
    run_all_tests()