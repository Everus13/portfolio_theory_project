import os
import sys
import json
import sqlite3
import numpy as np
import pandas as pd
from typing import Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Добавляем корень проекта в путь импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import (
    DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS, MODELS_DIR, ASSET_BOUNDS,
    REBALANCE_THRESHOLD
)
from src.storage.db_manager import get_connection, get_last_key_rate, get_last_date
from src.features.features_generator import build_features_and_targets
from src.optimization.optimization import optimize_portfolio
from daily_check import (
    PORTFOLIO_STATE_FILE, load_user_holdings, get_last_rebalance_info,
    save_rebalance_event, update_all_data
)
from catboost import CatBoostRegressor

app = FastAPI(title="Portfolio Theory API", version="1.0.0")

# Включаем CORS для связи с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HoldingsUpdate(BaseModel):
    holdings: Dict[str, float]

class DepositCalculation(BaseModel):
    amount: float

def get_current_portfolio_info():
    """Собирает всю актуальную аналитику портфеля."""
    holdings = load_user_holdings()
    
    # Получаем последние цены активов
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
                last_prices_date = row[0]
            else:
                current_prices[ticker] = 1.0
                
    # Расчет текущих весов
    portfolio_values = {}
    total_val = 0.0
    for t in PORTFOLIO_ASSETS:
        val = holdings.get(t, 0.0) * current_prices[t]
        portfolio_values[t] = val
        total_val += val
        
    current_weights = {}
    if total_val > 0:
        current_weights = {t: portfolio_values[t] / total_val for t in PORTFOLIO_ASSETS}
    else:
        current_weights = {t: 0.0 for t in PORTFOLIO_ASSETS}
        
    # Данные о прошлой ребалансировке
    last_rebalance_date, target_weights = get_last_rebalance_info()
    
    # Считаем прошедшие торговые дни
    query = "SELECT COUNT(DISTINCT date) FROM asset_prices WHERE ticker = 'TMON' AND date > ?"
    with get_connection(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (last_rebalance_date,))
        row = cursor.fetchone()
        trading_days_passed = row[0] if row else 0
        
    # Проверка триггеров
    time_trigger = (trading_days_passed >= 20)
    drift_trigger = False
    rebalance_reasons = []
    max_drift_ticker = None
    max_drift_val = 0.0
    
    if total_val > 0:
        for t in PORTFOLIO_ASSETS:
            drift = abs(current_weights[t] - target_weights.get(t, 0.25))
            if drift > max_drift_val:
                max_drift_val = drift
                max_drift_ticker = t
            if drift > REBALANCE_THRESHOLD:
                drift_trigger = True
                
        if time_trigger:
            rebalance_reasons.append("прошло более 20 торговых дней")
        if drift_trigger:
            rebalance_reasons.append(f"отклонение {max_drift_ticker} составило {max_drift_val*100:.2f}% (порог 5%)")
            
    rebalance_needed = time_trigger or drift_trigger
    key_rate = get_last_key_rate(DB_PATH, last_prices_date)
    
    # Получаем последний курс USD/RUB из БД
    usd_rate = 90.0
    query_usd = "SELECT close FROM asset_prices WHERE ticker = 'USD_RUB' AND close IS NOT NULL ORDER BY date DESC LIMIT 1"
    with get_connection(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query_usd)
        row = cursor.fetchone()
        if row:
            usd_rate = row[0]
            
    return {
        "holdings": holdings,
        "prices": current_prices,
        "values": portfolio_values,
        "total_value": total_val,
        "current_weights": current_weights,
        "target_weights": target_weights,
        "last_rebalance_date": last_rebalance_date,
        "trading_days_passed": trading_days_passed,
        "rebalance_needed": rebalance_needed,
        "rebalance_reasons": rebalance_reasons,
        "last_prices_date": last_prices_date,
        "key_rate": key_rate,
        "usd_rate": usd_rate
    }

@app.get("/api/portfolio")
def get_portfolio():
    """Получить текущее состояние портфеля."""
    try:
        # Пытаемся инкрементально обновить котировки при запросе
        update_all_data()
    except Exception as e:
        print(f"[Warning] Ошибка обновления котировок: {e}")
    return get_current_portfolio_info()

@app.post("/api/portfolio/holdings")
def update_holdings(payload: HoldingsUpdate):
    """Обновить количество лотов/паев в портфеле."""
    try:
        with open(PORTFOLIO_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload.holdings, f, indent=4)
        return get_current_portfolio_info()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/portfolio/calculate-deposit")
def calculate_deposit(payload: DepositCalculation):
    """Рассчитать распределение суммы пополнения по целевым весам."""
    info = get_current_portfolio_info()
    target_weights = info["target_weights"]
    current_prices = info["prices"]
    
    result = {}
    for t in PORTFOLIO_ASSETS:
        weight = target_weights.get(t, 0.25)
        allocated_rub = payload.amount * weight
        needed_lots = allocated_rub / current_prices[t]
        result[t] = {
            "weight": weight,
            "allocated_rub": allocated_rub,
            "needed_lots": needed_lots
        }
    return result

@app.post("/api/portfolio/rebalance")
def trigger_rebalance():
    """Запустить расчет ребалансировки по лучшим ML-параметрам."""
    info = get_current_portfolio_info()
    current_weights = info["current_weights"]
    current_prices = info["prices"]
    total_val = info["total_value"]
    last_prices_date = info["last_prices_date"]
    
    if total_val <= 0:
        raise HTTPException(status_code=400, detail="Невозможно ребалансировать пустой портфель")
        
    try:
        # Генерация признаков
        df_feat = build_features_and_targets(DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS)
        df_feat = df_feat[df_feat['date'] == last_prices_date].copy()
        
        feature_cols = [col for col in df_feat.columns if col not in [
            'date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 
            'daily_return', 'rvi_close', 'imoex_close', 'target'
        ]]
        
        # Лучшие параметры по результатам grid search тестов
        depth = 5
        iterations = 300
        lr = 0.01
        metric = 'sortino'
        
        predictions = []
        for t in PORTFOLIO_ASSETS:
            model_path = os.path.join(MODELS_DIR, f"catboost_{t}.cbm")
            if not os.path.exists(model_path):
                # Обучаем модель при ее отсутствии
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
        
        # Оценка ковариации
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
        
        risk_free_rate = info["key_rate"] / 100.0
        
        # Оптимизатор
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
        
        # Генерация сделок
        recommended_trades = []
        for t in PORTFOLIO_ASSETS:
            target_value = total_val * new_weights_dict[t]
            current_value = info["values"][t]
            delta_val = target_value - current_value
            delta_lots = delta_val / current_prices[t]
            
            recommended_trades.append({
                "ticker": t,
                "action": "КУПИТЬ" if delta_lots > 0 else "ПРОДАТЬ",
                "delta_rub": abs(delta_val),
                "delta_lots": abs(delta_lots),
                "target_weight": new_weights_dict[t],
                "current_weight": current_weights[t]
            })
            
        save_rebalance_event(last_prices_date, new_weights_dict)
        
        return {
            "success": True,
            "target_weights": new_weights_dict,
            "recommended_trades": recommended_trades,
            "rebalance_date": last_prices_date
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/portfolio/history")
def get_rebalance_history():
    """Получить логи ребалансировок."""
    query = "SELECT date, target_weights_json FROM portfolio_status ORDER BY date DESC"
    try:
        with get_connection(DB_PATH) as conn:
            df = pd.read_sql_query(query, conn)
        result = []
        for _, row in df.iterrows():
            result.append({
                "date": row["date"],
                "weights": json.loads(row["target_weights_json"])
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("main_api:app", host="127.0.0.1", port=8000, reload=True)

