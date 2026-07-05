import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from catboost import CatBoostRegressor

from config import DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS, MODELS_DIR, TRAIN_TEST_SPLIT_DATE
from src.features.features_generator import build_features_and_targets
from src.optimization.optimization import optimize_portfolio

def run_backtest():
    # 1. Загружаем датасет с фичами
    print("Генерация признаков...")
    df_all = build_features_and_targets(DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS)
    
    # Считаем ежедневную доходность каждого актива для ковариационной матрицы
    df_all['daily_return'] = df_all.groupby('ticker')['close'].pct_change()
    
    # 2. Выделяем тестовые даты
    df_test = df_all[df_all['date'] >= TRAIN_TEST_SPLIT_DATE].copy()
    test_dates = sorted(df_test['date'].unique())
    all_dates = sorted(df_all['date'].unique())
    
    if not test_dates:
        print("Нет данных для тестирования после указанной даты!")
        return
        
    print(f"Тестовый период: с {test_dates[0]} по {test_dates[-1]} ({len(test_dates)} дней)")
    
    # Загружаем CatBoost модели
    models = {}
    for ticker in PORTFOLIO_ASSETS:
        model_path = os.path.join(MODELS_DIR, f"catboost_{ticker}.cbm")
        models[ticker] = CatBoostRegressor()
        models[ticker].load_model(model_path)
        
    # Инициализируем переменные для отслеживания стоимости портфелей
    # Начинаем с 1.0 (100% капитала)
    portfolio_value = 1.0
    ew_portfolio_value = 1.0
    
    # Будем записывать стоимость на каждый день бэктеста
    portfolio_history = []
    ew_history = []
    market_history = []
    dates_history = []
    
    # Текущие веса
    weights = np.ones(len(PORTFOLIO_ASSETS)) / len(PORTFOLIO_ASSETS)
    ew_weights = np.ones(len(PORTFOLIO_ASSETS)) / len(PORTFOLIO_ASSETS)
    
    # Собираем цены закрытия активов на дату старта ребалансировки
    # (нужно для расчета стоимости внутри недели)
    base_prices = {}
    ew_base_prices = {}
    
    # Начальное значение индекса IMOEX
    df_imoex = df_all[['date', 'imoex_close']].drop_duplicates().sort_values('date').rename(columns={'imoex_close': 'close'})
    imoex_start_price = df_imoex[df_imoex['date'] >= test_dates[0]]['close'].iloc[0]
    
    rebalance_step = 5  # Ребалансировка раз в 5 рабочих дней (1 неделя)
    
    # Колонки признаков для моделей (должны совпадать с train.py)
    feature_cols = [col for col in df_all.columns if col not in [
        'date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 
        'daily_return', 'rvi_close', 'imoex_close', 'target'
    ]]
    
    for i, current_date in enumerate(test_dates):
        # 3. Ребалансировка раз в 5 дней
        if i % rebalance_step == 0:
            # Нам нужно рассчитать ковариационную матрицу за последние 60 торговых дней до current_date
            idx = all_dates.index(current_date)
            past_dates = all_dates[max(0, idx - 60):idx]
            
            # Вытягиваем цены для ковариации
            df_past = df_all[df_all['date'].isin(past_dates)]
            df_pivot = df_past.pivot(index='date', columns='ticker', values='daily_return')
            
            # Если не хватает данных для ковариации по какому-то активу, заполняем нулями
            df_pivot = df_pivot[PORTFOLIO_ASSETS].fillna(0.0)
            cov_matrix = df_pivot.cov().values
            cov_matrix_5d = cov_matrix * 5  # недельная ковариация
            
            # Делаем предсказания ожидаемых доходностей с помощью CatBoost
            predictions = []
            for ticker in PORTFOLIO_ASSETS:
                # Находим строку с признаками для этого тикера на текущую дату
                row = df_test[(df_test['date'] == current_date) & (df_test['ticker'] == ticker)]
                if not row.empty:
                    pred = models[ticker].predict(row[feature_cols])[0]
                else:
                    pred = 0.0  # Дефолтное значение, если данных нет
                predictions.append(pred)
                
            predictions = np.array(predictions)
            
            # Запускаем оптимизатор
            old_portfolio_value = portfolio_value
            old_ew_value = ew_portfolio_value
            
            weights = optimize_portfolio(predictions, cov_matrix_5d)
            ew_weights = np.ones(len(PORTFOLIO_ASSETS)) / len(PORTFOLIO_ASSETS)
            
            # Фиксируем цены закрытия на момент ребалансировки
            for ticker in PORTFOLIO_ASSETS:
                price_row = df_test[(df_test['date'] == current_date) & (df_test['ticker'] == ticker)]
                price = price_row['close'].iloc[0] if not price_row.empty else 1.0
                base_prices[ticker] = price
                ew_base_prices[ticker] = price
                
            print(f"Ребалансировка {current_date}: Веса = {dict(zip(PORTFOLIO_ASSETS, np.round(weights, 3)))}")
            
        # 4. Расчет ежедневной стоимости портфеля с учетом изменения цен активов внутри недели
        port_return_from_base = 0.0
        ew_return_from_base = 0.0
        
        for idx, ticker in enumerate(PORTFOLIO_ASSETS):
            price_row = df_test[(df_test['date'] == current_date) & (df_test['ticker'] == ticker)]
            current_price = price_row['close'].iloc[0] if not price_row.empty else base_prices[ticker]
            
            # Относительное изменение цены с момента последней ребалансировки
            asset_perf = (current_price / base_prices[ticker])
            port_return_from_base += weights[idx] * asset_perf
            
            ew_asset_perf = (current_price / ew_base_prices[ticker])
            ew_return_from_base += ew_weights[idx] * ew_asset_perf
            
        # Стоимость портфелей на текущий день
        daily_portfolio_value = old_portfolio_value * port_return_from_base
        daily_ew_value = old_ew_value * ew_return_from_base
        
        # Обновляем накопленное значение стоимости портфеля
        portfolio_value = daily_portfolio_value
        ew_portfolio_value = daily_ew_value
        
        # Получаем значение индекса IMOEX на текущий день для сравнения
        market_row = df_imoex[df_imoex['date'] == current_date]
        market_price = market_row['close'].iloc[0] if not market_row.empty else imoex_start_price
        market_value = market_price / imoex_start_price
        
        # Записываем историю
        portfolio_history.append(portfolio_value)
        ew_history.append(ew_portfolio_value)
        market_history.append(market_value)
        dates_history.append(current_date)
        
    # Создаем DataFrame с результатами бэктеста
    results = pd.DataFrame({
        'Date': pd.to_datetime(dates_history),
        'Strategy': portfolio_history,
        'EqualWeight': ew_history,
        'IMOEX': market_history
    })
    
    # 5. Расчет итоговых метрик эффективности
    def calculate_metrics(values, name):
        returns = pd.Series(values).pct_change().dropna()
        total_return = (values[-1] - 1.0) * 100
        ann_return = ((values[-1]) ** (252 / len(values)) - 1) * 100
        ann_vol = returns.std() * np.sqrt(252) * 100
        sharpe = ann_return / ann_vol if ann_vol > 0 else 0
        
        # Расчет максимальной просадки
        cum_max = pd.Series(values).cummax()
        drawdown = (pd.Series(values) - cum_max) / cum_max
        max_dd = drawdown.min() * 100
        
        print(f"\nМетрики для {name}:")
        print(f"  Общая доходность: {total_return:.2f}%")
        print(f"  Ануализированная доходность: {ann_return:.2f}%")
        print(f"  Ануализированная волатильность: {ann_vol:.2f}%")
        print(f"  Коэффициент Шарпа: {sharpe:.2f}")
        print(f"  Максимальная просадка: {max_dd:.2f}%")
        
    calculate_metrics(portfolio_history, "Нашей стратегии (CatBoost + MPT)")
    calculate_metrics(ew_history, "Равновзвешенного портфеля (Equal Weight)")
    calculate_metrics(market_history, "Рыночного индекса (IMOEX Buy & Hold)")
    
    # 6. Отрисовка графиков
    plt.figure(figsize=(12, 6))
    plt.plot(results['Date'], results['Strategy'], label='CatBoost + MPT Strategy', color='royalblue', linewidth=2)
    plt.plot(results['Date'], results['EqualWeight'], label='Equal Weight', color='orange', linestyle='--', linewidth=1.5)
    plt.plot(results['Date'], results['IMOEX'], label='IMOEX Index (Benchmark)', color='gray', linestyle=':', linewidth=1.5)
    
    plt.title("Сравнение доходности портфелей с 2025 года", fontsize=14)
    plt.xlabel("Дата", fontsize=12)
    plt.ylabel("Стоимость портфеля (отн. единицы)", fontsize=12)
    plt.legend(fontsize=10)
    plt.grid(True, linestyle=':', alpha=0.6)
    
    os.makedirs('notebooks', exist_ok=True)
    plot_path = 'notebooks/equity_curve.png'
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\nГрафик доходности сохранен по пути: {plot_path}")

if __name__ == '__main__':
    run_backtest()
