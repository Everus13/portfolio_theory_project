import os
import pandas as pd
from config import DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS
from src.storage.db_manager import init_db, save_prices, get_last_date
from src.parser.moex_client import (
    fetch_moex_history, fetch_yahoo_history, update_cbr_key_rate
)

def update_asset(db_path: str, ticker: str) -> None:
    """Обновляет котировки конкретного актива в БД."""
    last_date = get_last_date(db_path, ticker)
    start_date = last_date if last_date else '2020-01-01'
    
    if ticker == 'BTC':
        # Специфический парсинг для биткоина (Yahoo Finance)
        # Нам нужен BTC-USD и курс RUB=X
        btc_usd = fetch_yahoo_history('BTC-USD', start_date)
        rub_usd = fetch_yahoo_history('RUB=X', start_date)
        
        if btc_usd.empty or rub_usd.empty:
            print("[Warning] Не удалось получить данные по BTC-USD или курсу USD/RUB.")
            return
            
        btc_usd = btc_usd.set_index('date')
        rub_usd = rub_usd.set_index('date')
        
        # Переиндексируем курс под даты биткоина (выходные тоже заполняем)
        rub_usd_reindexed = rub_usd.reindex(btc_usd.index).ffill().bfill()
        
        # Пересчитываем в рубли
        btc_rub = pd.DataFrame(index=btc_usd.index)
        btc_rub['ticker'] = 'BTC'
        btc_rub['open'] = btc_usd['open'] * rub_usd_reindexed['close']
        btc_rub['high'] = btc_usd['high'] * rub_usd_reindexed['close']
        btc_rub['low'] = btc_usd['low'] * rub_usd_reindexed['close']
        btc_rub['close'] = btc_usd['close'] * rub_usd_reindexed['close']
        btc_rub['volume'] = btc_usd['volume']
        btc_rub = btc_rub.reset_index()
        
        save_prices(db_path, btc_rub)
        print(f"Успешно сохранено {len(btc_rub)} строк для BTC (в рубли).")
    else:
        # Стандартные котировки с Мосбиржи
        print(f"Загрузка с MOEX для {ticker} начиная с {start_date}...")
        df = fetch_moex_history(ticker, is_index=False, start_date=start_date)
        if not df.empty:
            save_prices(db_path, df)
            print(f"Успешно сохранено {len(df)} строк для {ticker}.")
        else:
            print(f"Нет новых данных для {ticker}.")

def update_benchmark(db_path: str, ticker: str) -> None:
    """Обновляет котировки бенчмарка (индекса) в БД."""
    last_date = get_last_date(db_path, ticker)
    start_date = last_date if last_date else '2020-01-01'
    
    print(f"Загрузка индекса с MOEX для {ticker} начиная с {start_date}...")
    df = fetch_moex_history(ticker, is_index=True, start_date=start_date)
    if not df.empty:
        save_prices(db_path, df)
        print(f"Успешно сохранено {len(df)} строк для бенчмарка {ticker}.")
    else:
        print(f"Нет новых данных для бенчмарка {ticker}.")

def main():
    print("Инициализация базы данных...")
    init_db(DB_PATH)
    
    print("\n1. Запуск обновления котировок активов портфеля...")
    for ticker in PORTFOLIO_ASSETS:
        update_asset(DB_PATH, ticker)
        
    print("\n2. Запуск обновления индексов (бенчмарков)...")
    for benchmark in BENCHMARKS:
        update_benchmark(DB_PATH, benchmark)
        
    print("\n3. Запуск обновления ключевой ставки ЦБ РФ...")
    update_cbr_key_rate(DB_PATH)
    
    print("\nВсе данные успешно обновлены!")

if __name__ == '__main__':
    main()
