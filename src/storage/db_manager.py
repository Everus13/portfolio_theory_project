import sqlite3
import pandas as pd
from typing import List, Optional

def get_connection(db_path: str) -> sqlite3.Connection:
    """Возвращает соединение с базой данных SQLite."""
    return sqlite3.connect(db_path)

def init_db(db_path: str) -> None:
    """Инициализирует таблицы цен активов и ключевой ставки ЦБ РФ."""
    query_prices = """
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
    query_rate = """
    CREATE TABLE IF NOT EXISTS cbr_key_rate (
        date TEXT PRIMARY KEY,
        rate REAL
    )
    """
    with get_connection(db_path) as conn:
        conn.execute(query_prices)
        conn.execute(query_rate)

def save_prices(db_path: str, df: pd.DataFrame) -> None:
    """Сохраняет DataFrame с ценами активов в БД."""
    if df.empty:
        return
    
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
    """Загружает цены активов из БД."""
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
    """Возвращает максимальную дату закрытия для тикера в БД."""
    query = "SELECT MAX(date) FROM asset_prices WHERE ticker = ?"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (ticker,))
        row = cursor.fetchone()
        return row[0] if row else None

def save_key_rate(db_path: str, df: pd.DataFrame) -> None:
    """Сохраняет историю ключевой ставки ЦБ РФ в БД."""
    if df.empty:
        return
    
    query = "INSERT OR REPLACE INTO cbr_key_rate (date, rate) VALUES (?, ?)"
    data_to_insert = df[['date', 'rate']].values.tolist()
    
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany(query, data_to_insert)

def load_key_rates(db_path: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
    """Загружает историю ключевых ставок из БД."""
    query = "SELECT * FROM cbr_key_rate WHERE 1=1"
    params = []
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
        
    query += " ORDER BY date ASC"
    
    with get_connection(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)

def get_last_key_rate(db_path: str, before_date: Optional[str] = None) -> float:
    """
    Возвращает последнюю ставку ЦБ на дату before_date или ранее.
    Если ставок в БД нет, возвращает дефолтное значение 15.0% из config.py.
    """
    from config import CBR_KEY_RATE_DEFAULT
    query = "SELECT rate FROM cbr_key_rate"
    params = []
    
    if before_date:
        query += " WHERE date <= ?"
        params.append(before_date)
        
    query += " ORDER BY date DESC LIMIT 1"
    
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, tuple(params))
        else:
            cursor.execute(query)
        row = cursor.fetchone()
        if row:
            return float(row[0])
            
    return CBR_KEY_RATE_DEFAULT
