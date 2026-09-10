"""
Tests for query date expression and range parser.
"""

from datetime import datetime, timedelta
import pytest

from chatybot.query.date_parser import parse_datetime_expr, parse_date_range


def test_parse_datetime_relative_words():
    ref_now = datetime(2026, 9, 10, 14, 30, 0)
    
    today = parse_datetime_expr("today", now=ref_now)
    assert today == datetime(2026, 9, 10, 0, 0, 0)
    
    yesterday = parse_datetime_expr("yesterday", now=ref_now)
    assert yesterday == datetime(2026, 9, 9, 0, 0, 0)
    
    thismonth = parse_datetime_expr("thismonth", now=ref_now)
    assert thismonth == datetime(2026, 9, 1, 0, 0, 0)
    
    lastmonth = parse_datetime_expr("lastmonth", now=ref_now)
    assert lastmonth == datetime(2026, 8, 1, 0, 0, 0)


def test_parse_datetime_relative_offsets():
    ref_now = datetime(2026, 9, 10, 14, 30, 0)
    
    d7 = parse_datetime_expr("7d", now=ref_now)
    assert d7 == ref_now - timedelta(days=7)
    
    h24 = parse_datetime_expr("24h", now=ref_now)
    assert h24 == ref_now - timedelta(hours=24)
    
    m30 = parse_datetime_expr("30m", now=ref_now)
    assert m30 == ref_now - timedelta(minutes=30)


def test_parse_datetime_standard_formats():
    dt1 = parse_datetime_expr("2026-03-01")
    assert dt1 == datetime(2026, 3, 1, 0, 0, 0)
    
    dt2 = parse_datetime_expr("03/01/2026")
    assert dt2 == datetime(2026, 3, 1, 0, 0, 0)
    
    dt3 = parse_datetime_expr("2026-03-01 15:45:00")
    assert dt3 == datetime(2026, 3, 1, 15, 45, 0)


def test_parse_date_range():
    ref_now = datetime(2026, 9, 10, 12, 0, 0)
    
    start, end = parse_date_range("03/01/2026 to 05/01/2026", now=ref_now)
    assert start == datetime(2026, 3, 1, 0, 0, 0)
    assert end == datetime(2026, 5, 1, 23, 59, 59)
    
    start2, end2 = parse_date_range("2026-03-01..2026-05-01", now=ref_now)
    assert start2 == datetime(2026, 3, 1, 0, 0, 0)
    assert end2 == datetime(2026, 5, 1, 23, 59, 59)
