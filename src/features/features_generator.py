import pandas as pd
import numpy as np
from src.storage.db_manager import load_prices

def build_features_and_targets(db_path: str, portfolio_assets: list, benchmarks: list) -> pd.DataFrame:
    """
    Загружает данные из БД, объединяет их и генерирует признаки для CatBoost.
    """
    # 1. Загрузка цен для активов портфеля
    df_assets = load_prices(db_path, portfolio_assets)
    
    # 2. Загрузка цен для бенчмарков (RVI и IMOEX)
    df_benchmarks = load_prices(db_path, benchmarks)
    
    # Выделяем RVI и IMOEX в отдельные фреймы для слияния
    df_rvi = df_benchmarks[df_benchmarks['ticker'] == 'RVI'][['date', 'close']].rename(columns={'close': 'rvi_close'})
    df_imoex = df_benchmarks[df_benchmarks['ticker'] == 'IMOEX'][['date', 'close']].rename(columns={'close': 'imoex_close'})
    
    # 3. Слияние (Merge) с активами по дате
    df = pd.merge(df_assets, df_rvi, on='date', how='left')
    df = pd.merge(df, df_imoex, on='date', how='left')
    
    # Сортируем по тикеру и дате для корректных расчетов
    df = df.sort_values(['ticker', 'date']).reset_index(drop=True)
    
    # Заполняем пропуски в индексах (если они есть)
    df['rvi_close'] = df.groupby('ticker')['rvi_close'].ffill()
    df['imoex_close'] = df.groupby('ticker')['imoex_close'].ffill()
    
    # 4. Расчет признаков (Features)
    
    # Обычная дневная доходность актива (нужна для расчета волатильности)
    df['daily_return'] = df.groupby('ticker')['close'].pct_change(1)
    
    # Лаги доходности актива за 1, 2, 5, 10, 20 дней
    for lag in [1, 2, 5, 10, 20]:
        df[f'return_lag_{lag}'] = df.groupby('ticker')['close'].pct_change(lag)
        
    # Историческая волатильность актива за последние 5, 10, 20 дней
    for window in [5, 10, 20]:
        df[f'volatility_{window}'] = df.groupby('ticker')['daily_return'].transform(
            lambda x: x.rolling(window).std()
        )
        
    # Фичи индекса волатильности RVI
    # а) Текущее значение RVI
    # б) Отношение RVI к его скользящему среднему за 5, 10, 20 дней (режим паники/спокойствия рынка)
    for window in [5, 10, 20]:
        rvi_ma = df.groupby('ticker')['rvi_close'].transform(lambda x: x.rolling(window).mean())
        df[f'rvi_ratio_{window}'] = df['rvi_close'] / rvi_ma
        
    # Фичи индекса IMOEX (доходность всего рынка за последние 5 и 20 дней)
    df['imoex_return_5'] = df.groupby('ticker')['imoex_close'].pct_change(5)
    df['imoex_return_20'] = df.groupby('ticker')['imoex_close'].pct_change(20)
    
    # 5. Расчет таргета (Target): доходность за СЛЕДУЮЩИЕ 5 торговых дней
    # Формула: (Close_t+5 - Close_t) / Close_t
    # В pandas это сдвиг назад на 5 элементов внутри группы тикера
    df['target'] = df.groupby('ticker')['close'].shift(-5) / df['close'] - 1
    
    # Удаляем строки, где нет достаточного количества истории для расчета фичей (начальные строки с NaN)
    # Таргет в конце (последние 5 дней) НЕ удаляем здесь, так как они нужны для прогнозирования будущего
    df = df.dropna(subset=['return_lag_20', 'volatility_20', 'rvi_ratio_20']).reset_index(drop=True)
    
    return df
