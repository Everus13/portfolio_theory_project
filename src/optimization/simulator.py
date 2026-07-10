import os
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from config import ASSET_BOUNDS
from src.features.features_generator import build_features_and_targets
from src.optimization.optimization import optimize_portfolio
from src.storage.db_manager import get_last_key_rate

def run_simulation(
    db_path: str,
    tickers: list,
    benchmarks: list,
    start_date: str,
    depth: int = 5,
    iterations: int = 600,
    learning_rate: float = 0.01,
    retrain_interval: int = None,       # в торговых днях (None, 10, 20, 60, 120)
    metric: str = 'sharpe',             # 'sharpe' или 'sortino'
    turnover_penalty_coeff: float = 0.0,
    transaction_fee: float = 0.001       # 0.1% комиссия за сделку (в долях)
) -> dict:
    """
    Универсальный движок бэктестинга и симуляции с поддержкой:
    1. Ребалансировки раз в месяц (20 дней) ИЛИ при отклонении весов > 5%.
    2. Скользящего переобучения (борьба с Data Drift).
    3. Учета транзакционных издержек.
    4. Оптимизации Шарпа/Сортино.
    """
    # 1. Загрузка данных и генерация фичей
    df_all = build_features_and_targets(db_path, tickers, benchmarks)
    df_all['daily_return'] = df_all.groupby('ticker')['close'].pct_change()
    
    # Разделяем на исторические и тестовые даты
    df_test = df_all[df_all['date'] >= start_date].copy()
    test_dates = sorted(df_test['date'].unique())
    all_dates = sorted(df_all['date'].unique())
    
    if not test_dates:
        return {'success': False, 'message': 'Нет тестовых данных после start_date'}
        
    feature_cols = [col for col in df_all.columns if col not in [
        'date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 
        'daily_return', 'rvi_close', 'imoex_close', 'target'
    ]]
    
    # 2. Инициализация моделей (обучаем первую версию до start_date)
    models = {}
    
    def train_models_up_to(train_end_date: str):
        df_train_sub = df_all[(df_all['date'] < train_end_date) & df_all['target'].notna()].copy()
        for t in tickers:
            df_ticker = df_train_sub[df_train_sub['ticker'] == t]
            if df_ticker.empty:
                continue
            X = df_ticker[feature_cols]
            y = df_ticker['target']
            
            # Разделяем 80/20 для early stopping
            split_idx = int(len(X) * 0.8)
            X_tr, y_tr = X.iloc[:split_idx], y.iloc[:split_idx]
            X_val, y_val = X.iloc[split_idx:], y.iloc[split_idx:]
            
            model = CatBoostRegressor(
                iterations=iterations,
                depth=depth,
                learning_rate=learning_rate,
                loss_function='RMSE',
                random_seed=42,
                verbose=0
            )
            
            if len(X_val) > 5:
                model.fit(X_tr, y_tr, eval_set=(X_val, y_val), early_stopping_rounds=30, verbose=0)
            else:
                model.fit(X, y, verbose=0)
                
            models[t] = model

    # Обучаем первичные модели
    train_models_up_to(start_date)
    
    # 3. Инициализация переменных симуляции
    portfolio_value = 1.0
    ew_portfolio_value = 1.0
    
    portfolio_history = []
    ew_history = []
    market_history = []
    dates_history = []
    
    # Стартовые веса (номинальные)
    weights = np.array([ASSET_BOUNDS[t][0] for t in tickers])  # берем минимальный вес как старт
    weights = weights / np.sum(weights)  # нормируем
    
    # Целевые веса ребалансировки (к которым мы ребалансируем)
    target_weights = weights.copy()
    
    # Равновзвешенные веса для бенчмарка
    ew_weights = np.ones(len(tickers)) / len(tickers)
    
    # Исходная точка для сравнения с IMOEX
    df_imoex = df_all[['date', 'imoex_close']].drop_duplicates().sort_values('date')
    imoex_start_price = df_imoex[df_imoex['date'] >= start_date]['imoex_close'].iloc[0]
    
    days_since_rebalance = 0
    days_since_training = 0
    
    # 4. Основной дневной цикл симуляции
    for i, current_date in enumerate(test_dates):
        # а) Получаем доходности активов за сегодняшний день
        daily_returns = []
        for t in tickers:
            row = df_test[(df_test['date'] == current_date) & (df_test['ticker'] == t)]
            r = row['daily_return'].iloc[0] if not row.empty else 0.0
            daily_returns.append(r)
        daily_returns = np.array(daily_returns)
        
        # б) Обновляем стоимость равновзвешенного портфеля (Equal Weight)
        # Он ребалансируется раз в месяц без комиссий для сравнения
        if days_since_rebalance == 0:
            ew_weights = np.ones(len(tickers)) / len(tickers)
            
        ew_port_return = np.dot(ew_weights, daily_returns)
        ew_portfolio_value = ew_portfolio_value * (1 + ew_port_return)
        
        # Обновляем дрейф весов равновзвешенного портфеля
        ew_weights = ew_weights * (1 + daily_returns)
        if np.sum(ew_weights) > 0:
            ew_weights = ew_weights / np.sum(ew_weights)
            
        # в) Обновляем стоимость нашей стратегии
        port_return = np.dot(weights, daily_returns)
        portfolio_value = portfolio_value * (1 + port_return)
        
        # Обновляем дрейф весов нашей стратегии
        weights = weights * (1 + daily_returns)
        if np.sum(weights) > 0:
            weights = weights / np.sum(weights)
            
        # г) Проверяем условия ребалансировки
        # Триггер 1: Прошел месяц (20 торговых дней)
        time_trigger = (days_since_rebalance >= 20)
        # Триггер 2: Отклонение любого актива от целевого веса > 5%
        drift_trigger = np.any(np.abs(weights - target_weights) > 0.05)
        
        if time_trigger or drift_trigger:
            # --- РЕБАЛАНСИРОВКА ---
            # 1. Проверяем необходимость переобучения моделей (Data Drift)
            if retrain_interval is not None and days_since_training >= retrain_interval:
                train_models_up_to(current_date)
                days_since_training = 0
                
            # 2. Оцениваем ковариацию за последние 60 дней
            idx_all = all_dates.index(current_date)
            past_dates = all_dates[max(0, idx_all - 60):idx_all]
            df_past = df_all[df_all['date'].isin(past_dates)]
            df_pivot = df_past.pivot(index='date', columns='ticker', values='daily_return')
            df_pivot = df_pivot[tickers].fillna(0.0)
            cov_matrix = df_pivot.cov().values
            cov_matrix_5d = cov_matrix * 5  # масштабируем к неделе
            
            # Для Сортино получаем матрицу исторических доходностей
            historical_returns_matrix = df_pivot.values # shape (T, N)
            
            # 3. Делаем прогнозы доходности CatBoost на неделю вперед
            predictions = []
            for t in tickers:
                row = df_test[(df_test['date'] == current_date) & (df_test['ticker'] == t)]
                if not row.empty and t in models:
                    pred = models[t].predict(row[feature_cols])[0]
                else:
                    pred = 0.0
                predictions.append(pred)
            predictions = np.array(predictions)
            
            # 4. Загружаем текущую ставку ЦБ РФ из базы данных
            risk_free_rate = get_last_key_rate(db_path, current_date) / 100.0
            
            # 5. Оптимизируем веса
            new_weights = optimize_portfolio(
                tickers=tickers,
                expected_returns=predictions,
                cov_matrix=cov_matrix_5d,
                historical_returns=historical_returns_matrix,
                risk_free_rate=risk_free_rate,
                metric=metric,
                previous_weights=weights,
                turnover_penalty_coeff=turnover_penalty_coeff
            )
            
            # 6. Учитываем транзакционные издержки (комиссия за сделку)
            turnover = np.sum(np.abs(new_weights - weights))
            fee_cost = portfolio_value * transaction_fee * turnover
            portfolio_value -= fee_cost
            
            # Обновляем веса
            weights = new_weights.copy()
            target_weights = new_weights.copy()
            
            # Сбрасываем счетчик дней ребалансировки
            days_since_rebalance = 0
        else:
            # Увеличиваем счетчик дней
            days_since_rebalance += 1
            
        if retrain_interval is not None:
            days_since_training += 1
            
        # д) Записываем историю рынка (IMOEX)
        market_row = df_imoex[df_imoex['date'] == current_date]
        market_price = market_row['imoex_close'].iloc[0] if not market_row.empty else imoex_start_price
        market_value = market_price / imoex_start_price
        
        # Записываем состояние на конец дня
        portfolio_history.append(portfolio_value)
        ew_history.append(ew_portfolio_value)
        market_history.append(market_value)
        dates_history.append(current_date)
        
    # 5. Расчет итоговых метрик
    def get_metrics_dict(values):
        returns = pd.Series(values).pct_change().dropna()
        total_return = (values[-1] - 1.0) * 100
        ann_return = ((values[-1]) ** (252 / len(values)) - 1) * 100
        ann_vol = returns.std() * np.sqrt(252) * 100
        
        # Downside волатильность
        downside_returns = returns[returns < 0]
        ann_down_vol = downside_returns.std() * np.sqrt(252) * 100
        
        sharpe = ann_return / ann_vol if ann_vol > 0 else 0
        sortino = ann_return / ann_down_vol if ann_down_vol > 0 else 0
        
        # Максимальная просадка
        cum_max = pd.Series(values).cummax()
        drawdown = (pd.Series(values) - cum_max) / cum_max
        max_dd = drawdown.min() * 100
        
        return {
            'total_return': total_return,
            'ann_return': ann_return,
            'ann_vol': ann_vol,
            'sharpe': sharpe,
            'sortino': sortino,
            'max_dd': max_dd
        }
        
    return {
        'success': True,
        'dates': dates_history,
        'strategy_values': portfolio_history,
        'ew_values': ew_history,
        'market_values': market_history,
        'strategy_metrics': get_metrics_dict(portfolio_history),
        'ew_metrics': get_metrics_dict(ew_history),
        'market_metrics': get_metrics_dict(market_history)
    }
