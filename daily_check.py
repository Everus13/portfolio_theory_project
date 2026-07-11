import os
import json
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime

from config import (
    DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS, MODELS_DIR, ASSET_BOUNDS,
    REBALANCE_THRESHOLD, CBR_KEY_RATE_DEFAULT
)
from src.storage.db_manager import (
    get_connection, get_last_date, get_last_key_rate, save_prices
)
from src.parser.moex_client import (
    fetch_moex_history, fetch_yahoo_history, update_cbr_key_rate
)
from src.features.features_generator import build_features_and_targets
from src.optimization.optimization import optimize_portfolio
from catboost import CatBoostRegressor

# Файл с текущими активами инвестора
PORTFOLIO_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'portfolio_state.json')

def update_all_data():
    """Обновляет все данные на сегодняшний день."""
    print("Обновление котировок с бирж...")
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 1. Обновляем котировки активов
    for ticker in PORTFOLIO_ASSETS:
        last_date = get_last_date(DB_PATH, ticker)
        start_date = last_date if last_date else '2020-01-01'
        
        if ticker == 'BTC':
            btc_usd = fetch_yahoo_history('BTC-USD', start_date)
            rub_usd = fetch_yahoo_history('RUB=X', start_date)
            if not btc_usd.empty and not rub_usd.empty:
                # Сохраняем также курс доллара в базу под тикером USD_RUB
                usd_rub_df = rub_usd.copy()
                usd_rub_df['ticker'] = 'USD_RUB'
                save_prices(DB_PATH, usd_rub_df)
                
                btc_usd = btc_usd.set_index('date')
                rub_usd = rub_usd.set_index('date')
                rub_usd_reindexed = rub_usd.reindex(btc_usd.index).ffill().bfill()
                
                btc_rub = pd.DataFrame(index=btc_usd.index)
                btc_rub['ticker'] = 'BTC'
                btc_rub['open'] = btc_usd['open'] * rub_usd_reindexed['close']
                btc_rub['high'] = btc_usd['high'] * rub_usd_reindexed['close']
                btc_rub['low'] = btc_usd['low'] * rub_usd_reindexed['close']
                btc_rub['close'] = btc_usd['close'] * rub_usd_reindexed['close']
                btc_rub['volume'] = btc_usd['volume']
                btc_rub = btc_rub.reset_index()
                save_prices(DB_PATH, btc_rub)
        else:
            df = fetch_moex_history(ticker, is_index=False, start_date=start_date)
            if not df.empty:
                save_prices(DB_PATH, df)
                
    # 2. Обновляем котировки индексов
    for benchmark in BENCHMARKS:
        last_date = get_last_date(DB_PATH, benchmark)
        start_date = last_date if last_date else '2020-01-01'
        df = fetch_moex_history(benchmark, is_index=True, start_date=start_date)
        if not df.empty:
            save_prices(DB_PATH, df)
            
    # 3. Обновляем ставку ЦБ РФ
    update_cbr_key_rate(DB_PATH)

def init_portfolio_status():
    """Создает таблицу для хранения статуса последнего ребаланса."""
    query = """
    CREATE TABLE IF NOT EXISTS portfolio_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        target_weights_json TEXT
    )
    """
    with get_connection(DB_PATH) as conn:
        conn.execute(query)

def get_last_rebalance_info():
    """Возвращает дату последней ребалансировки и целевые веса."""
    init_portfolio_status()
    query = "SELECT date, target_weights_json FROM portfolio_status ORDER BY date DESC LIMIT 1"
    with get_connection(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        row = cursor.fetchone()
        if row:
            return row[0], json.loads(row[1])
    # Дефолтная начальная точка (защитный портфель)
    default_weights = {
        'TPAY': 0.40,
        'TGLD': 0.35,
        'BTC': 0.15,
        'TMON': 0.10
    }
    return '2020-01-01', default_weights

def save_rebalance_event(date_str: str, target_weights: dict):
    """Сохраняет событие ребалансировки в БД."""
    init_portfolio_status()
    query = "INSERT INTO portfolio_status (date, target_weights_json) VALUES (?, ?)"
    with get_connection(DB_PATH) as conn:
        conn.execute(query, (date_str, json.dumps(target_weights)))

def load_user_holdings() -> dict:
    """Загружает текущие активы инвестора (количество единиц/паев)."""
    if not os.path.exists(PORTFOLIO_STATE_FILE):
        default_state = {
            'TPAY': 0.0,
            'TGLD': 0.0,
            'BTC': 0.0,
            'TMON': 0.0
        }
        with open(PORTFOLIO_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_state, f, indent=4)
        print(f"\n[Info] Создан пустой файл портфеля: {PORTFOLIO_STATE_FILE}")
        print("Пожалуйста, заполните его вашим текущим количеством лотов перед использованием!")
        return default_state
        
    with open(PORTFOLIO_STATE_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def run_production_check():
    # 1. Обновляем котировки до сегодняшнего дня
    update_all_data()
    
    # 2. Загружаем текущие остатки пользователя
    holdings = load_user_holdings()
    
    # 3. Получаем последние цены активов из БД
    current_prices = {}
    last_prices_date = None
    for ticker in PORTFOLIO_ASSETS:
        query = "SELECT date, close FROM asset_prices WHERE ticker = ? AND close IS NOT NULL ORDER BY date DESC LIMIT 1"
        with get_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (ticker,))
            row = cursor.fetchone()
            if row:
                current_prices[ticker] = row[1]
                last_prices_date = row[0]  # берем самую свежую дату
            else:
                current_prices[ticker] = 1.0
            
    print(f"\nПоследние цены в БД (актуальность: ~{last_prices_date}):")
    for t in PORTFOLIO_ASSETS:
        print(f"  - {t}: {current_prices[t]:,.2f} RUB")
        
    # Рассчитываем текущие стоимости и веса
    portfolio_values = {}
    total_portfolio_value = 0.0
    for t in PORTFOLIO_ASSETS:
        val = holdings.get(t, 0.0) * current_prices[t]
        portfolio_values[t] = val
        total_portfolio_value += val
        
    if total_portfolio_value <= 0:
        print("\n[Warning] Суммарная стоимость портфеля равна 0. Заполните portfolio_state.json!")
        return
        
    current_weights = {}
    print(f"\nТекущее состояние портфеля (Общая стоимость: {total_portfolio_value:,.2f} ₽):")
    for t in PORTFOLIO_ASSETS:
        w = portfolio_values[t] / total_portfolio_value
        current_weights[t] = w
        print(f"  • {t}: {holdings.get(t, 0.0):,.4f} лотов | {portfolio_values[t]:,.2f} ₽ ({w*100:.2f}%)")
        
    # 4. Получаем данные о последней ребалансировке
    last_rebalance_date, target_weights = get_last_rebalance_info()
    print(f"\nПоследняя ребалансировка была: {last_rebalance_date}")
    
    # Считаем количество прошедших торговых дней
    query = "SELECT COUNT(DISTINCT date) FROM asset_prices WHERE ticker = 'TMON' AND date > ?"
    with get_connection(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (last_rebalance_date,))
        row = cursor.fetchone()
        trading_days_passed = row[0] if row else 0
    print(f"Прошло торговых дней: {trading_days_passed}")
    
    # 5. Проверяем условия триггера
    # Условие 1: Прошел месяц (>= 20 торговых дней)
    time_trigger = (trading_days_passed >= 20)
    # Условие 2: Отклонение доли > 5%
    drift_trigger = False
    max_drift_ticker = None
    max_drift_val = 0.0
    for t in PORTFOLIO_ASSETS:
        drift = abs(current_weights[t] - target_weights.get(t, 0.25))
        if drift > max_drift_val:
            max_drift_val = drift
            max_drift_ticker = t
        if drift > REBALANCE_THRESHOLD:
            drift_trigger = True
            
    print(f"Максимальное отклонение доли: {max_drift_ticker} на {max_drift_val*100:.2f}% (целевая: {target_weights.get(max_drift_ticker, 0.0)*100:.2f}%)")
    
    rebalance_needed = time_trigger or drift_trigger
    
    if rebalance_needed:
        print("\n🚨 ТРЕБУЕТСЯ РЕБАЛАНСИРОВКА!")
        if time_trigger:
            print("  -> Причина: Прошло более 20 торговых дней.")
        if drift_trigger:
            print(f"  -> Причина: Отклонение актива {max_drift_ticker} превысило 5% порог.")
            
        # 6. Запускаем предсказание и оптимизацию
        # Шаг А: Сбор признаков для сегодняшнего дня
        df_feat = build_features_and_targets(DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS)
        df_feat = df_feat[df_feat['date'] == last_prices_date].copy()
        
        feature_cols = [col for col in df_feat.columns if col not in [
            'date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 
            'daily_return', 'rvi_close', 'imoex_close', 'target'
        ]]
        
        # Лучшие параметры по результатам grid search тестов (защитный портфель)
        depth = 5
        iterations = 300
        lr = 0.01
        metric = 'sortino'
        
        # Проверяем, обучены ли модели. Если нет - обучаем на всей истории
        predictions = []
        for t in PORTFOLIO_ASSETS:
            model_path = os.path.join(MODELS_DIR, f"catboost_{t}.cbm")
            if not os.path.exists(model_path):
                print(f"Обучение модели для {t}...")
                df_train = build_features_and_targets(DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS)
                df_train_sub = df_train[(df_train['ticker'] == t) & df_train['target'].notna()]
                
                model = CatBoostRegressor(iterations=iterations, depth=depth, learning_rate=lr, loss_function='RMSE', random_seed=42, verbose=0)
                model.fit(df_train_sub[feature_cols], df_train_sub['target'])
                model.save_model(model_path)
            
            model = CatBoostRegressor()
            model.load_model(model_path)
            row_feat = df_feat[df_feat['ticker'] == t]
            pred = model.predict(row_feat[feature_cols])[0] if not row_feat.empty else 0.0
            predictions.append(pred)
            
        predictions = np.array(predictions)
        
        # Получаем ковариацию за последние 60 дней
        df_all_prices = build_features_and_targets(DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS)
        df_all_prices['daily_return'] = df_all_prices.groupby('ticker')['close'].pct_change()
        all_dates_list = sorted(df_all_prices['date'].unique())
        idx_all = all_dates_list.index(last_prices_date)
        past_dates = all_dates_list[max(0, idx_all - 60):idx_all]
        df_past = df_all_prices[df_all_prices['date'].isin(past_dates)]
        df_pivot = df_past.pivot(index='date', columns='ticker', values='daily_return')
        df_pivot = df_pivot[PORTFOLIO_ASSETS].fillna(0.0)
        
        cov_matrix_5d = df_pivot.cov().values * 5
        historical_returns_matrix = df_pivot.values
        
        # Ставка ЦБ РФ
        risk_free_rate = get_last_key_rate(DB_PATH, last_prices_date) / 100.0
        
        # Оптимизация
        current_w_array = np.array([current_weights[t] for t in PORTFOLIO_ASSETS])
        new_w_array = optimize_portfolio(
            tickers=PORTFOLIO_ASSETS,
            expected_returns=predictions,
            cov_matrix=cov_matrix_5d,
            historical_returns=historical_returns_matrix,
            risk_free_rate=risk_free_rate,
            metric=metric,
            previous_weights=current_w_array,
            turnover_penalty_coeff=0.001
        )
        
        new_weights_dict = dict(zip(PORTFOLIO_ASSETS, new_w_array))
        
        print("\n=== Новые оптимальные веса ===")
        for t in PORTFOLIO_ASSETS:
            print(f"  • {t}: {new_weights_dict[t]*100:.2f}% (было: {current_weights[t]*100:.2f}%)")
            
        # 7. Расчет необходимых торговых сделок
        print("\n📋 РЕКОМЕНДУЕМЫЕ СДЕЛКИ:")
        for t in PORTFOLIO_ASSETS:
            target_val = total_portfolio_value * new_weights_dict[t]
            current_val = portfolio_values[t]
            delta_val = target_val - current_val  # в рублях
            delta_lots = delta_val / current_prices[t]  # в штуках актива
            
            action = "КУПИТЬ" if delta_lots > 0 else "ПРОДАТЬ"
            print(f"  • {action} {t} на сумму {abs(delta_val):,.2f} ₽ (~ {abs(delta_lots):,.4f} лотов/паев)")
            
        # Записываем событие ребалансировки
        save_rebalance_event(last_prices_date, new_weights_dict)
        print(f"\n[Success] Событие ребалансировки записано в БД под датой {last_prices_date}.")
        
    else:
        print("\n✅ Ребалансировка не требуется. Отклонения весов в пределах нормы (порог 5%).")

if __name__ == '__main__':
    run_production_check()
