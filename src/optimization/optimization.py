import numpy as np
from scipy.optimize import minimize
from config import ASSET_BOUNDS

def calculate_portfolio_volatility(weights: np.ndarray, cov_matrix: np.ndarray) -> float:
    """Рассчитывает стандартное отклонение (волатильность) портфеля."""
    return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

def calculate_portfolio_downside_deviation(
    weights: np.ndarray, 
    historical_returns: np.ndarray, 
    risk_free_rate_daily: float = 0.0
) -> float:
    """
    Рассчитывает downside волатильность портфеля (для коэффициента Сортино).
    Формула: sqrt( mean( min(0, R_p - R_f_daily)^2 ) )
    """
    # historical_returns имеет форму (T, N), где T - дни, N - активы
    portfolio_returns = np.dot(historical_returns, weights)
    # Отрицательные отклонения ниже безрисковой ставки
    downside_diff = np.minimum(0.0, portfolio_returns - risk_free_rate_daily)
    mean_square = np.mean(downside_diff ** 2)
    return np.sqrt(mean_square)

def optimize_portfolio(
    tickers: list,
    expected_returns: np.ndarray,
    cov_matrix: np.ndarray,
    historical_returns: np.ndarray = None,  # исторические доходности (T, N) для Сортино
    risk_free_rate: float = 0.0,            # годовая безрисковая ставка
    metric: str = 'sharpe',                 # 'sharpe' или 'sortino'
    previous_weights: np.ndarray = None,    # предыдущие веса для штрафа за оборот
    turnover_penalty_coeff: float = 0.0     # коэффициент штрафа за ребаланс
) -> np.ndarray:
    """
    Находит оптимальные веса портфеля, максимизирующие коэффициент Шарпа или Сортино.
    Дополнительно учитывает штраф за транзакционные издержки (оборот).
    """
    num_assets = len(expected_returns)
    risk_free_rate_daily = risk_free_rate / 252.0  # дневная безрисковая ставка
    
    # 1. Целевая функция
    def objective_function(weights):
        # Доходность за неделю (предполагаем expected_returns за 5 дней)
        portfolio_return = np.dot(weights, expected_returns)
        
        if metric == 'sortino' and historical_returns is not None:
            # Считаем downside отклонение
            portfolio_risk = calculate_portfolio_downside_deviation(
                weights, historical_returns, risk_free_rate_daily
            )
            # Масштабируем до недельного риска (умножаем на sqrt(5))
            portfolio_risk = portfolio_risk * np.sqrt(5)
        else:
            # Стандартная волатильность за неделю
            portfolio_risk = calculate_portfolio_volatility(weights, cov_matrix)
            
        # Защита от деления на ноль
        if portfolio_risk < 1e-7:
            return 0.0
            
        # Отношение доходности за вычетом ставки к риску
        # (риск-фри ставка тоже масштабируется до недельной: годовая / 252 * 5)
        rf_week = risk_free_rate_daily * 5
        ratio = (portfolio_return - rf_week) / portfolio_risk
        
        # Общий лосс = -Коэффициент (т.к. minimize минимизирует)
        loss = -ratio
        
        # Штраф за ребаланс (Turnover Penalty)
        if previous_weights is not None and turnover_penalty_coeff > 0:
            turnover = np.sum(np.abs(weights - previous_weights))
            loss += turnover_penalty_coeff * turnover
            
        return loss

    # 2. Начальное приближение (равные веса, нормированные)
    initial_weights = np.ones(num_assets) / num_assets
    
    # 3. Ограничение: сумма весов равна 1.0
    constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0})
    
    # 4. Динамические границы для каждого актива из config.py
    bounds_list = []
    for ticker in tickers:
        if ticker in ASSET_BOUNDS:
            bounds_list.append(ASSET_BOUNDS[ticker])
        else:
            bounds_list.append((0.0, 1.0))  # дефолтные границы, если тикер неизвестен
    bounds = tuple(bounds_list)
    
    # 5. Запуск оптимизатора
    result = minimize(
        objective_function, 
        initial_weights, 
        method='SLSQP', 
        bounds=bounds, 
        constraints=constraints
    )
    
    if not result.success:
        print("[Warning] Оптимизатор не смог найти решение:", result.message)
        # В случае ошибки возвращаем веса, пропорциональные номинальным
        nominal_weights = []
        for ticker in tickers:
            nominal_weights.append(ASSET_BOUNDS.get(ticker, (0.0, 1.0))[0]) # минимальный вес как бэкап
        # нормируем
        nominal_weights = np.array(nominal_weights)
        if np.sum(nominal_weights) > 0:
            return nominal_weights / np.sum(nominal_weights)
        return initial_weights
        
    return result.x
