import requests
import pandas as pd
import time
import xml.etree.ElementTree as ET
import yfinance as yf
from typing import Optional
from config import DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS
from src.storage.db_manager import save_prices, get_last_date, save_key_rate

def fetch_with_retry(url: str, params: dict, max_retries: int = 5, backoff_factor: float = 1.0) -> requests.Response:
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            if attempt == max_retries - 1:
                raise e
            sleep_time = backoff_factor * (2 ** attempt)
            print(f"\n[Warning] Ошибка подключения: {e}. Повтор {attempt + 2}/{max_retries} через {sleep_time}с...")
            time.sleep(sleep_time)

def fetch_moex_history(ticker: str, is_index: bool = False, start_date: str = '2020-01-01') -> pd.DataFrame:
    """
    Загружает историю котировок для тикера с MOEX ISS.
    У фондов (TPAY, TGLD, TMON) фильтрует BOARDID == 'TQTF'.
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
        
        history_data = data_json.get('history', {})
        columns = history_data.get('columns', [])
        rows = history_data.get('data', [])
        
        if not rows:
            break
            
        df = pd.DataFrame(rows, columns=columns)
        all_dfs.append(df)
        
        if len(rows) < 100:
            break
            
        start += 100
        time.sleep(0.15)
        
    if not all_dfs:
        return pd.DataFrame()
        
    full_df = pd.concat(all_dfs, ignore_index=True)
    
    # Фильтруем по доске
    if 'BOARDID' in full_df.columns:
        if ticker in ['TPAY', 'TGLD', 'TMON']:
            full_df = full_df[full_df['BOARDID'] == 'TQTF']
        else:
            # Для акций по умолчанию TQBR
            full_df = full_df[full_df['BOARDID'] == 'TQBR']
    
    rename_map = {
        'TRADEDATE': 'date',
        'SECID': 'ticker',
        'OPEN': 'open',
        'HIGH': 'high',
        'LOW': 'low',
        'CLOSE': 'close',
        'VOLUME': 'volume'
    }
    
    full_df = full_df.rename(columns=rename_map)
    required_cols = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']
    
    for col in required_cols:
        if col not in full_df.columns:
            full_df[col] = 0.0
            
    processed_df = full_df[required_cols].copy()
    
    numeric_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in numeric_cols:
        processed_df[col] = pd.to_numeric(processed_df[col], errors='coerce')
        
    processed_df['date'] = processed_df['date'].astype(str)
    processed_df['ticker'] = processed_df['ticker'].astype(str)
    
    processed_df = processed_df.dropna(subset=['open', 'close'])
    processed_df = processed_df.sort_values('date').reset_index(drop=True)
    
    return processed_df

def fetch_yahoo_history(ticker: str, start_date: str = '2020-01-01') -> pd.DataFrame:
    """Загружает историю котировок с Yahoo Finance с помощью yfinance."""
    print(f"Загрузка с Yahoo Finance для {ticker} начиная с {start_date}...")
    try:
        df = yf.download(ticker, start=start_date, progress=False)
        if df.empty:
            return pd.DataFrame()
            
        df = df.reset_index()
        
        # Если колонки мульти-индексные, сглаживаем их
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]
            
        rename_map = {
            'Date': 'date',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        }
        df = df.rename(columns=rename_map)
        df['ticker'] = ticker
        
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        required_cols = ['date', 'ticker', 'open', 'high', 'low', 'close', 'volume']
        df = df[required_cols].copy()
        
        # Приводим к типам
        numeric_cols = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        df = df.dropna(subset=['open', 'close']).sort_values('date').reset_index(drop=True)
        return df
    except Exception as e:
        print(f"[Warning] Ошибка при загрузке {ticker} с Yahoo: {e}")
        return pd.DataFrame()

def fetch_cbr_key_rate(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Загружает историю ключевых ставок ЦБ РФ через SOAP веб-сервис.
    """
    url = 'https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx'
    headers = {'content-type': 'text/xml', 'User-Agent': 'Mozilla/5.0'}
    
    # SOAP XML тело
    body = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <KeyRateXML xmlns="http://web.cbr.ru/">
      <fromDate>{start_date}T00:00:00</fromDate>
      <ToDate>{end_date}T23:59:59</ToDate>
    </KeyRateXML>
  </soap:Body>
</soap:Envelope>'''
    
    try:
        r = requests.post(url, data=body, headers=headers, timeout=12)
        r.raise_for_status()
        
        root = ET.fromstring(r.text)
        records = []
        for elem in root.iter():
            if elem.tag.endswith('KR'):
                date_val = None
                rate_val = None
                for child in elem:
                    if child.tag.endswith('DT'):
                        date_val = child.text.split('T')[0]
                    elif child.tag.endswith('Rate'):
                        rate_val = float(child.text)
                if date_val and rate_val is not None:
                    records.append({'date': date_val, 'rate': rate_val})
        
        if records:
            df = pd.DataFrame(records)
            df = df.sort_values('date').reset_index(drop=True)
            return df
    except Exception as e:
        print(f"[Warning] Ошибка обращения к API ЦБ РФ: {e}")
    
    return pd.DataFrame()

def update_cbr_key_rate(db_path: str, default_start_date: str = '2020-01-01') -> None:
    """Инкрементально скачивает и обновляет историю ставки ЦБ РФ в БД."""
    query = "SELECT MAX(date) FROM cbr_key_rate"
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query)
            row = cursor.fetchone()
            last_date = row[0] if row else None
        except sqlite3.OperationalError:
            # Таблица еще не создана
            last_date = None
            
    start_date = last_date if last_date else default_start_date
    # Заканчиваем сегодняшним днем
    end_date = time.strftime('%Y-%m-%d')
    
    print(f"Загрузка ставки ЦБ с {start_date} по {end_date}...")
    df = fetch_cbr_key_rate(start_date, end_date)
    if not df.empty:
        save_key_rate(db_path, df)
        print(f"Ключевая ставка успешно обновлена: {len(df)} записей добавлено.")
    else:
        print("Не удалось обновить ставку ЦБ из API (или нет новых данных). Будет использоваться последнее значение из БД или дефолт.")

import sqlite3
