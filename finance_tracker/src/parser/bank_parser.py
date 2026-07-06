import pandas as pd
from finance_tracker.config import BANK_COLUMNS_MAP

def parse_bank_csv(file_path: str) -> pd.DataFrame:
    """
    Считывает CSV выписку банка, переименовывает и чистит колонки.
    Возвращает DataFrame с колонками: date, description, amount, category, is_auto.
    """
    # 1. Читаем файл с учетом возможной кодировки cp1251
    try:
        df = pd.read_csv(file_path, sep=';', encoding='cp1251')
    except Exception:
        df = pd.read_csv(file_path, sep=';', encoding='utf-8')
        
    # 2. Переименовываем колонки по нашей карте из config.py
    df = df.rename(columns=BANK_COLUMNS_MAP)
    
    # Оставляем только нужные колонки
    required_cols = ['date', 'description', 'amount', 'category']
    # Если какой-то колонки нет в выписке, заполняем ее пустыми значениями
    for col in required_cols:
        if col not in df.columns:
            df[col] = None
            
    df = df[required_cols].copy()
    
    # 3. Чистим числовой столбец amount (суммы)
    # Удаляем пробелы, меняем запятые на точки и приводим к float
    df['amount'] = df['amount'].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.')
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    
    # 4. Приводим дату к формату YYYY-MM-DD HH:MM:SS
    df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
    df['date'] = df['date'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Удаляем записи с пустыми критическими полями (дата или описание)
    df = df.dropna(subset=['date', 'description']).copy()
    
    # 5. Выставляем флаг авто-разметки в 0 (так как данные пришли напрямую из банка)
    df['is_auto'] = 0
    
    # Если категория не указана банком, запишем "Прочее"
    df['category'] = df['category'].fillna("Прочее")
    
    return df
