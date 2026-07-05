import requests
import pandas as pd
import time
from typing import Optional
from config import STOCKS, FUNDS, DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS
from src.storage.db_manager import save_prices, get_last_date

def fetch_with_retry(url: str, params: dict, max_retries: int = 5, backoff_factor: float = 1.0) -> requests.Response:
    for attempt in range(max_retries):
        try:
            # Увеличиваем таймаут запроса до 15 секунд
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            if attempt == max_retries - 1:
                raise e
            sleep_time = backoff_factor * (2 ** attempt)
            print(f"\n[Warning] Ошибка подключения к MOEX API: {e}. Повторная попытка {attempt + 2}/{max_retries} через {sleep_time}с...")
            time.sleep(sleep_time)

def fetch_moex_history(ticker: str, is_index: bool = False, start_date: str = '2020-01-01') -> pd.DataFrame:
    """
    Загружает всю историю котировок для тикера с MOEX ISS начиная со start_date.
    Пагинирует запросы по 100 записей (параметр start=...).
    Возвращает DataFrame с колонками: date, ticker, open, high, low, close, volume.
    """
    market = 'index' if is_index else 'shares'
    url = f"https://iss.moex.com/iss/history/engines/stock/markets/{market}/securities/{ticker}.json"
    
    all_dfs = []
    start = 0
    
    while True:
        params = {
            'from': start_date,
            'start': start,
            'iss.meta': 'off'
        }
        
        response = fetch_with_retry(url, params)
        data_json = response.json()
        
        # Получаем данные истории
        history_data = data_json.get('history', {})
        columns = history_data.get('columns', [])
        rows = history_data.get('data', [])
        
        if not rows:
            break  # Данных больше нет
            
        df = pd.DataFrame(rows, columns=columns)
        all_dfs.append(df)
        
        # Если пришло меньше 100 строк, значит это была последняя страница
        if len(rows) < 100:
            break
            
        start += 100
        time.sleep(0.15)  # Небольшая задержка для API
        
    if not all_dfs:
        return pd.DataFrame()
        
    full_df = pd.concat(all_dfs, ignore_index=True)
    
    # Фильтруем по BOARDID для акций (TQBR) и фондов (TQTF), чтобы исключить другие режимы торгов и валюты (например, USD-доски)
    if 'BOARDID' in full_df.columns:
        if ticker in STOCKS:
            full_df = full_df[full_df['BOARDID'] == 'TQBR']
        elif ticker in FUNDS:
            full_df = full_df[full_df['BOARDID'] == 'TQTF']
    
    # Маппинг колонок под схему БД
    rename_map = {
        'TRADEDATE': 'date',
        'SECID': 'ticker',
        'OPEN': 'open',
        'HIGH': 'high',
        'LOW': 'low',
        'CLOSE': 'close',
        'VOLUME': 'volume'
    }
    
    # Переименовываем
    full_df = full_df.rename(columns=rename_map)
    
    # Оставляем только нужные колонки
    required_cols = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']
    
    # Если каких-то колонок нет (например, volume у некоторых индексов), создаем их
    for col in required_cols:
        if col not in full_df.columns:
            full_df[col] = 0.0
            
    processed_df = full_df[required_cols].copy()
    
    # Преобразуем типы данных в числовые
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce')
        
    # Приводим дату к строке
    processed_df['date'] = processed_df['date'].astype(str)
    processed_df['ticker'] = processed_df['ticker'].astype(str)
    
    # Удаляем неторговые дни, где нет цен закрытия/открытия
    processed_df = processed_df.dropna(subset=['open', 'close'])
    
    # Сортируем по дате
    processed_df = processed_df.sort_values('date').reset_index(drop=True)
    
    return processed_df

def update_database(db_path: str, ticker: str, is_index: bool = False, default_start_date: str = '2020-01-01') -> None:
    """
    Инкрементально обновляет базу данных для указанного тикера.
    """
    last_date = get_last_date(db_path, ticker)
    if last_date:
        # Начинаем с последней известной даты (save_prices перезапишет ее, обновив данные за этот день)
        start_date = last_date
    else:
        start_date = default_start_date
        
    print(f"Загрузка данных для {ticker} начиная с {start_date}...")
    df = fetch_moex_history(ticker, is_index, start_date)
    
    if not df.empty:
        save_prices(db_path, df)
        print(f"Успешно сохранено {len(df)} строк для {ticker}.")
    else:
        print(f"Нет новых данных для {ticker}.")
