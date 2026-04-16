# Historical Marketplace Data Layer
# Stores scanned KDP data for trend analysis

import sqlite3
import os
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class ListingEntry:
    """A single marketplace listing record"""
    id: str
    title: str
    niche: str
    listing_date: date
    price: float
    royalty: float
    units_sold: int
    kenp_pages: int
    marketplace: str  # amazon.com, amazon.co.uk, etc.
    category: Optional[str] = None
    keywords: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'niche': self.niche,
            'listing_date': self.listing_date.isoformat(),
            'price': self.price,
            'royalty': self.royalty,
            'units_sold': self.units_sold,
            'kenp_pages': self.kenp_pages,
            'marketplace': self.marketplace,
            'category': self.category,
            'keywords': self.keywords or [],
            'metadata': self.metadata or {},
        }
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'ListingEntry':
        return cls(
            id=d['id'],
            title=d['title'],
            niche=d['niche'],
            listing_date=date.fromisoformat(d['listing_date']),
            price=float(d['price']),
            royalty=float(d['royalty']),
            units_sold=int(d['units_sold']),
            kenp_pages=int(d['kenp_pages']),
            marketplace=d['marketplace'],
            category=d.get('category'),
            keywords=d.get('keywords'),
            metadata=d.get('metadata'),
        )

class HistoricalStore:
    """SQLite-backed storage for marketplace historical data"""
    
    _table = 'listings'
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from hermes_constants import get_hermes_home
            hermes_home = get_hermes_home()
            db_path = str(hermes_home / 'planner.db')
        self.db_path = Path(db_path)
        self._ensure_connection()
        self._init_schema()
    
    @property
    def connection(self):
        if not hasattr(self, '_conn') or self._conn is None:
            self._ensure_connection()
        return self._conn
    
    def _ensure_connection(self):
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
    
    def _init_schema(self):
        cursor = self.connection.cursor()
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self._table} (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                niche TEXT NOT NULL,
                listing_date TEXT NOT NULL,
                price REAL NOT NULL,
                royalty REAL NOT NULL,
                units_sold INTEGER NOT NULL,
                kenp_pages INTEGER NOT NULL,
                marketplace TEXT NOT NULL,
                category TEXT,
                keywords TEXT,  -- JSON array
                metadata TEXT  -- JSON object
            )
        ''')
        # Index for common queries
        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_niche ON {self._table}(niche)')
        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_date ON {self._table}(listing_date)')
        cursor.execute(f'CREATE INDEX IF NOT EXISTS idx_marketplace ON {self._table}(marketplace)')
        self.connection.commit()
    
    def upsert(self, entry: ListingEntry) -> None:
        """Insert or update a listing"""
        cursor = self.connection.cursor()
        cursor.execute(f'''
            INSERT OR REPLACE INTO {self._table} 
            (id, title, niche, listing_date, price, royalty, units_sold, kenp_pages, marketplace, category, keywords, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry.id,
            entry.title,
            entry.niche,
            entry.listing_date.isoformat(),
            entry.price,
            entry.royalty,
            entry.units_sold,
            entry.kenp_pages,
            entry.marketplace,
            entry.category,
            json.dumps(entry.keywords) if entry.keywords else None,
            json.dumps(entry.metadata) if entry.metadata else None,
        ))
        self.connection.commit()
    
    def bulk_upsert(self, entries: List[ListingEntry]) -> None:
        """Upsert multiple listings at once"""
        cursor = self.connection.cursor()
        cursor.executemany(f'''
            INSERT OR REPLACE INTO {self._table} 
            (id, title, niche, listing_date, price, royalty, units_sold, kenp_pages, marketplace, category, keywords, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            (
                e.id, e.title, e.niche, e.listing_date.isoformat(), 
                e.price, e.royalty, e.units_sold, e.kenp_pages,
                e.marketplace, e.category,
                json.dumps(e.keywords) if e.keywords else None,
                json.dumps(e.metadata) if e.metadata else None,
            )
            for e in entries
        ])
        self.connection.commit()
        logger.info(f"Upserted {len(entries)} listings")
    
    def get_all(self) -> List[ListingEntry]:
        """Get all listings"""
        cursor = self.connection.cursor()
        cursor.execute(f'SELECT * FROM {self._table}')
        rows = cursor.fetchall()
        return [self._row_to_entry(r) for r in rows]
    
    def query_by_niche(self, niche: str) -> List[ListingEntry]:
        """Get all listings for a specific niche"""
        cursor = self.connection.cursor()
        cursor.execute(f'SELECT * FROM {self._table} WHERE niche = ?', (niche,))
        rows = cursor.fetchall()
        return [self._row_to_entry(r) for r in rows]
    
    def query_by_date_range(self, start: date, end: date) -> List[ListingEntry]:
        """Get listings within a date range"""
        cursor = self.connection.cursor()
        cursor.execute(f'''
            SELECT * FROM {self._table} 
            WHERE listing_date >= ? AND listing_date <= ?
            ORDER BY listing_date DESC
        ''', (start.isoformat(), end.isoformat()))
        rows = cursor.fetchall()
        return [self._row_to_entry(r) for r in rows]
    
    def get_top_performing_niches(self, n: int = 10, min_listings: int = 3) -> List[Dict[str, Any]]:
        """Get top niches by average ROI (royalty/kenp) with minimum listing count"""
        cursor = self.connection.cursor()
        cursor.execute(f'''
            SELECT 
                niche,
                COUNT(*) as listing_count,
                AVG(royalty) as avg_royalty,
                AVG(kenp_pages) as avg_kenp,
                AVG(royalty / kenp_pages) as avg_roi,
                SUM(units_sold) as total_units,
                MIN(listing_date) as first_listing,
                MAX(listing_date) as last_listing
            FROM {self._table}
            GROUP BY niche
            HAVING listing_count >= ?
            ORDER BY avg_roi DESC
            LIMIT ?
        ''', (min_listings, n))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'niche': row['niche'],
                'listing_count': row['listing_count'],
                'avg_royalty': round(row['avg_royalty'], 2),
                'avg_kenp': round(row['avg_kenp'], 1),
                'avg_roi': round(row['avg_roi'], 4),
                'total_units': row['total_units'],
                'time_range': f"{row['first_listing']} to {row['last_listing']}",
            })
        return results
    
    def get_recent_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get trending niches in recent period"""
        end_date = date.today()
        start_date = date.today() - timedelta(days=days)
        
        cursor = self.connection.cursor()
        cursor.execute(f'''
            SELECT 
                niche,
                COUNT(*) as listing_count,
                AVG(royalty) as avg_royalty,
                AVG(kenp_pages) as avg_kenp,
                SUM(units_sold) as total_units
            FROM {self._table}
            WHERE listing_date >= ?
            GROUP BY niche
            HAVING listing_count >= 2
            ORDER BY total_units DESC
            LIMIT 10
        ''', (start_date.isoformat(),))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'niche': row['niche'],
                'listing_count': row['listing_count'],
                'avg_royalty': round(row['avg_royalty'], 2),
                'avg_kenp': round(row['avg_kenp'], 1),
                'total_units': row['total_units'],
            })
        return results
    
    def _row_to_entry(self, row: sqlite3.Row) -> ListingEntry:
        return ListingEntry(
            id=row['id'],
            title=row['title'],
            niche=row['niche'],
            listing_date=date.fromisoformat(row['listing_date']),
            price=row['price'],
            royalty=row['royalty'],
            units_sold=row['units_sold'],
            kenp_pages=row['kenp_pages'],
            marketplace=row['marketplace'],
            category=row['category'],
            keywords=json.loads(row['keywords']) if row['keywords'] else None,
            metadata=json.loads(row['metadata']) if row['metadata'] else None,
        )
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self, '_conn'):
            self._conn.close()
            self._conn = None
