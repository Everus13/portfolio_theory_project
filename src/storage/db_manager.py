import sqlite3
import pandas as pd
from typing import List, Optional

def get_connection(db_path: str) -> sqlite3.Connection:
    """Возвращает соединение с базой данных SQLite."""
    return sqlite3.connect(db_path)

def init_db(db_path: str) -> None:
    query = """
    CREATE TABLE IF NOT EXISTS asset_prices (
        date TEXT,
        ticker TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume REAL,
        PRIMARY KEY (date, ticker)
    )
    """
    with get_connection(db_path) as conn:
        conn.execute(query)


def save_prices(db_path: str, df: pd.DataFrame) -> None:
    if df.empty:
        return
    
    # Отбираем нужные колонки в правильном порядке
    cols = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']
    data_to_insert = df[cols].values.tolist()
    
    query = """
    INSERT OR REPLACE INTO asset_prices (date, ticker, open, high, low, close, volume)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(query, data_to_insert)


def load_prices(db_path: str, tickers: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
    if not tickers:
        return pd.DataFrame()
        
    placeholders = ', '.join(['?'] * len(tickers))
    query = f"SELECT * FROM asset_prices WHERE ticker IN ({placeholders})"
    params = list(tickers)
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
        
    query += " ORDER BY date ASC"
    
    with get_connection(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_last_date(db_path: str, ticker: str) -> Optional[str]:
    query = "SELECT MAX(date) FROM asset_prices WHERE ticker = ?"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (ticker,))
        row = cursor.fetchone()
        return row[0] if row else None

