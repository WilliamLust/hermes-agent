"""
KDP XLSX Parser Module

Parses Amazon KDP Dashboard and Prior Month Royalties XLSX files.
Returns structured data ready for metrics calculation.

Fixed 2026-04-15:
  - Prior month parser: header is row 0 ('Sales Period'), actual headers at row 1,
    data starts at row 2. Old code used positional indexing on wrong rows.
  - Dashboard parser: uses named columns from header row correctly.
  - Error handling: all exceptions surfaced with full message, not swallowed.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


def load_kdp_dashboard(filepath: Path) -> Optional[Dict[str, Any]]:
    """
    Parse KDP_Dashboard-*.xlsx file.

    Sheets used:
      Combined Sales — per-book sales with named columns
      KENP Read      — per-book KENP with named columns
      Summary        — aggregate totals

    Returns dict with 'books', 'kenp_data', 'date_range', 'summary'.
    """
    try:
        xl = pd.ExcelFile(filepath)
        result = {
            'date_range': None,
            'summary': {},
            'books': [],
            'kenp_data': []
        }

        # --- Summary sheet ---
        if 'Summary' in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name='Summary')
            if len(df) > 0:
                row = df.iloc[0]
                result['date_range'] = str(row.get('Date', 'Unknown'))
                result['summary'] = {
                    'paid_units_ebook':   int(row.get('Paid Units Sold (eBook)', 0) or 0),
                    'free_units_ebook':   int(row.get('Free Units Sold (eBook)', 0) or 0),
                    'net_units_paperback': int(row.get('Net Units Sold (Paperback)', 0) or 0),
                    'kenp_read_total':    int(row.get('Kindle Edition Normalized Page (KENP) Read', 0) or 0),
                    'royalty_usd':        float(row.get('Royalty (USD)', 0) or 0),
                }

        # --- Combined Sales sheet (has named columns, one header row) ---
        if 'Combined Sales' in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name='Combined Sales')
            for _, row in df.iterrows():
                title = str(row.get('Title', '') or '')
                if not title or title == 'nan':
                    continue
                result['books'].append({
                    'title':            title,
                    'author':           str(row.get('Author Name', '') or ''),
                    'asin':             str(row.get('ASIN/ISBN', '') or ''),
                    'marketplace':      str(row.get('Marketplace', 'Amazon.com') or 'Amazon.com'),
                    'royalty_type':     str(row.get('Royalty Type', '') or ''),
                    'transaction_type': str(row.get('Transaction Type', '') or ''),
                    'units_sold':       int(row.get('Units Sold', 0) or 0),
                    'units_refunded':   int(row.get('Units Refunded', 0) or 0),
                    'net_units':        int(row.get('Net Units Sold', 0) or 0),
                    'avg_list_price':   float(row.get('Avg. List Price without tax', 0) or 0),
                    'royalty_amount':   float(row.get('Royalty', 0) or 0),
                    'currency':         str(row.get('Royalty Currency', 'USD') or 'USD'),
                    'sale_date':        str(row.get('Royalty Date', '') or ''),
                })

        # --- KENP Read sheet (named columns) ---
        if 'KENP Read' in xl.sheet_names:
            df = pd.read_excel(xl, sheet_name='KENP Read')
            kenp_col = 'Kindle Edition Normalized Page (KENP) Read'
            for _, row in df.iterrows():
                title = str(row.get('Title', '') or '')
                if not title or title == 'nan':
                    continue
                result['kenp_data'].append({
                    'title':       title,
                    'author':      str(row.get('Author Name', '') or ''),
                    'asin':        str(row.get('ASIN', '') or ''),
                    'marketplace': str(row.get('Marketplace', 'Amazon.com') or 'Amazon.com'),
                    'kenp_pages':  int(row.get(kenp_col, 0) or 0),
                    'date':        str(row.get('Date', '') or ''),
                })

        return result

    except Exception as e:
        print("Error parsing dashboard file %s: %s" % (filepath.name, e))
        return None


def load_kdp_prior_month(filepath: Path) -> Optional[Dict[str, Any]]:
    """
    Parse KDP_Prior_Month_Royalties-*.xlsx file.

    Real file structure (confirmed from XLSX inspection):
      Row 0: ['Sales Period', 'March 2026', NaN, ...]   ← period header, skip
      Row 1: ['Title', 'Author', 'ASIN', ...]            ← actual column headers
      Row 2+: data rows

    Sheets: eBook Royalty, KENP Read, Paperback Royalty, Total Earnings
    We prefer eBook Royalty + KENP Read (most granular).
    """
    try:
        xl = pd.ExcelFile(filepath)
        result = {
            'date_range': None,
            'books': [],
            'kenp_data': []
        }

        # --- eBook Royalty sheet ---
        # Row 0 = period header, row 1 = column names, rows 2+ = data
        if 'eBook Royalty' in xl.sheet_names:
            raw = pd.read_excel(xl, sheet_name='eBook Royalty', header=None)
            if len(raw) >= 1:
                # Period info from row 0, col 1
                period_val = raw.iloc[0, 1] if raw.shape[1] > 1 else None
                if period_val and str(period_val) != 'nan':
                    result['date_range'] = str(period_val)

            if len(raw) >= 2:
                # Row 1 = actual headers
                headers = [str(h) for h in raw.iloc[1]]
                # Data rows start at index 2
                data = raw.iloc[2:].copy()
                data.columns = headers
                data = data.reset_index(drop=True)

                for _, row in data.iterrows():
                    title = str(row.get('Title', '') or '')
                    if not title or title == 'nan':
                        continue
                    result['books'].append({
                        'title':          title,
                        'author':         str(row.get('Author', '') or ''),
                        'asin':           str(row.get('ASIN', '') or ''),
                        'marketplace':    str(row.get('Marketplace', 'Amazon.com') or 'Amazon.com'),
                        'units_sold':     int(float(row.get('Units Sold', 0) or 0)),
                        'units_refunded': int(float(row.get('Units Refunded', 0) or 0)),
                        'net_units':      int(float(row.get('Net Units Sold', 0) or 0)),
                        'royalty_type':   str(row.get('Royalty Type', '') or ''),
                        'currency':       str(row.get('Currency', 'USD') or 'USD'),
                        'avg_list_price': float(row.get('Avg. List Price without tax', 0) or 0),
                        'avg_offer_price': float(row.get('Avg. Offer Price without tax', 0) or 0),
                        'delivery_cost':  float(row.get('Avg. Delivery Cost', 0) or 0),
                        'royalty_amount': float(row.get('Royalty', 0) or 0),
                        'format':         'eBook',
                    })

        # --- KENP Read sheet (same header structure) ---
        if 'KENP Read' in xl.sheet_names:
            raw = pd.read_excel(xl, sheet_name='KENP Read', header=None)
            if len(raw) >= 2:
                headers = [str(h) for h in raw.iloc[1]]
                data = raw.iloc[2:].copy()
                data.columns = headers
                data = data.reset_index(drop=True)

                kenp_col = 'Kindle Edition Normalized Page (KENP) Read'
                for _, row in data.iterrows():
                    title = str(row.get('Title', '') or '')
                    if not title or title == 'nan':
                        continue
                    result['kenp_data'].append({
                        'title':       title,
                        'author':      str(row.get('Author', '') or ''),
                        'asin':        str(row.get('ASIN', '') or ''),
                        'marketplace': str(row.get('Marketplace', 'Amazon.com') or 'Amazon.com'),
                        'kenp_pages':  int(float(row.get(kenp_col, 0) or 0)),
                    })

        # --- Paperback Royalty (same header structure) ---
        if 'Paperback Royalty' in xl.sheet_names:
            raw = pd.read_excel(xl, sheet_name='Paperback Royalty', header=None)
            if len(raw) >= 3:
                headers = [str(h) for h in raw.iloc[1]]
                data = raw.iloc[2:].copy()
                data.columns = headers
                data = data.reset_index(drop=True)

                for _, row in data.iterrows():
                    title = str(row.get('Title', '') or '')
                    if not title or title == 'nan':
                        continue
                    result['books'].append({
                        'title':          title,
                        'author':         str(row.get('Author', '') or ''),
                        'asin':           str(row.get('ASIN', '') or ''),
                        'marketplace':    str(row.get('Marketplace', 'Amazon.com') or 'Amazon.com'),
                        'units_sold':     int(float(row.get('Units Sold', 0) or 0)),
                        'net_units':      int(float(row.get('Net Units Sold', 0) or 0)),
                        'royalty_type':   str(row.get('Royalty Type', '') or ''),
                        'currency':       str(row.get('Currency', 'USD') or 'USD'),
                        'avg_list_price': float(row.get('Avg. List Price without tax', 0) or 0),
                        'royalty_amount': float(row.get('Royalty', 0) or 0),
                        'format':         'Paperback',
                    })

        return result

    except Exception as e:
        import traceback
        print("Error parsing prior month file %s: %s" % (filepath.name, e))
        traceback.print_exc()
        return None


def discover_kdp_files(directory: Path) -> Dict[str, List[Path]]:
    """Find all KDP XLSX files in directory."""
    result = {'dashboard': [], 'prior_month': []}
    if not directory.exists():
        print("WARNING: KDP directory not found: %s" % directory)
        return result
    for f in directory.glob("*.xlsx"):
        name_upper = f.name.upper()
        if 'KDP_DASHBOARD' in name_upper:
            result['dashboard'].append(f)
        elif 'PRIOR_MONTH' in name_upper or 'PRIOR' in name_upper:
            result['prior_month'].append(f)
    return result


def parse_all_kdp_files(directory: Path = Path("/home/bookforge/Downloads")) -> Dict[str, Any]:
    """
    Parse all KDP files and return unified structured data.

    Returns:
        {
            'all_books': list of book dicts,
            'all_kenp':  list of KENP dicts,
            'source_files': dict,
            'dashboard_data': dict or None,
            'prior_month_data': dict or None,
        }
    """
    files = discover_kdp_files(directory)
    result = {
        'dashboard_data': None,
        'prior_month_data': None,
        'all_books': [],
        'all_kenp': [],
        'source_files': {},
    }

    # Dashboard (current month)
    if files['dashboard']:
        latest = sorted(files['dashboard'])[-1]
        result['source_files']['dashboard'] = latest
        data = load_kdp_dashboard(latest)
        result['dashboard_data'] = data
        if data:
            for book in data.get('books', []):
                book['_source'] = 'dashboard'
                result['all_books'].append(book)
            for k in data.get('kenp_data', []):
                k['_source'] = 'dashboard'
                result['all_kenp'].append(k)
            print("  Dashboard: %d books, %d KENP records from %s" % (
                len(data.get('books', [])), len(data.get('kenp_data', [])), latest.name))
    else:
        print("  WARNING: No KDP Dashboard file found in %s" % directory)

    # Prior month
    if files['prior_month']:
        latest = sorted(files['prior_month'])[-1]
        result['source_files']['prior_month'] = latest
        data = load_kdp_prior_month(latest)
        result['prior_month_data'] = data
        if data:
            for book in data.get('books', []):
                book['_source'] = 'prior_month'
                result['all_books'].append(book)
            for k in data.get('kenp_data', []):
                k['_source'] = 'prior_month'
                result['all_kenp'].append(k)
            print("  Prior month: %d books, %d KENP records from %s" % (
                len(data.get('books', [])), len(data.get('kenp_data', [])), latest.name))
    else:
        print("  WARNING: No Prior Month file found in %s" % directory)

    return result
