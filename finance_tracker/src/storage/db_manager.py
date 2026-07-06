import sqlite3
import pandas as pd
from typing import Optional
from finance_tracker.config import DB_PATH

def get_connection() -> sqlite3.Connection:
    """Возвращает соединение с БД SQLite."""
    return sqlite3.connect(DB_PATH)

def init_db() -> None:
    """
    Создает таблицу transactions, если она не существует.
    """
    query = """
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        description TEXT,
        amount REAL,
        category TEXT,
        is_auto INTEGER,
        UNIQUE(date, description, amount)
    )
    """
    with get_connection() as conn:
        conn.execute(query)

def save_transactions(df: pd.DataFrame) -> int:
    """
    Сохраняет DataFrame с транзакциями в БД.
    Ожидаемые колонки: date, description, amount, category, is_auto.
    Использует конструкцию INSERT OR IGNORE, чтобы не дублировать транзакции.
    Возвращает количество успешно вставленных записей.
    """
    if df.empty:
        return 0
        
    query = """
    INSERT OR IGNORE INTO transactions (date, description, amount, category, is_auto)
    VALUES (?, ?, ?, ?, ?)
    """
    cols = ['date', 'description', 'amount', 'category', 'is_auto']
    data_list = df[cols].values.tolist()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(query, data_list)
        return conn.total_changes

def load_all_transactions() -> pd.DataFrame:
    """Загружает всю историю транзакций из БД в DataFrame, сортируя по дате от новых к старым."""
    query = "SELECT * FROM transactions ORDER BY date DESC"
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)

def load_training_data() -> pd.DataFrame:
    """
    Загружает только те транзакции, которые размечены человеком (is_auto = 0),
    для последующего переобучения модели CatBoost.
    """
    query = "SELECT description, category FROM transactions WHERE is_auto = 0"
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)
