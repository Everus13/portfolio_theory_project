import numpy as np
from scipy.optimize import minimize
from config import MIN_WEIGHT, MAX_WEIGHT

def calculate_portfolio_volatility(weights: np.ndarray, cov_matrix: np.ndarray) -> float:
    """
    Рассчитывает стандартное отклонение (волатильность) портфеля.
    Формула: sqrt(w^T * Sigma * w)
    """
    return np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

def optimize_portfolio(expected_returns: np.ndarray, cov_matrix: np.ndarray, risk_free_rate: float = 0.0) -> np.ndarray:
    """
    Находит оптимальные веса портфеля, максимизирующие коэффициент Шарпа.
    Вход:
        expected_returns: массив прогнозируемых доходностей по каждому активу (размер N)
        cov_matrix: ковариационная матрица (размер N x N)
        risk_free_rate: безрисковая ставка за период
    Выход:
        Массив оптимальных весов (размер N)
    """
    num_assets = len(expected_returns)
    
    # 1. Целевая функция: отрицательный коэффициент Шарпа
    def objective_function(weights):
        portfolio_return = np.dot(weights, expected_returns)
        portfolio_vol = calculate_portfolio_volatility(weights, cov_matrix)
        
        # Защита от деления на ноль
        if portfolio_vol < 1e-7:
            return 0.0
            
        sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_vol
        return -sharpe_ratio  # Минимизируем отрицательный Шарп
        
    # 2. Начальное приближение (равные веса)
    initial_weights = np.ones(num_assets) / num_assets
    
    # 3. Ограничение: сумма весов равна 1.0 (eq - equality constraint)
    constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0})
    
    # 4. Границы для весов: каждый вес должен быть в рамках от MIN_WEIGHT (0.05) до MAX_WEIGHT (1.0)
    bounds = tuple((MIN_WEIGHT, MAX_WEIGHT) for _ in range(num_assets))
    
    # 5. Запуск оптимизатора Scipy
    # Метод SLSQP (Sequential Least Squares Programming) отлично подходит для задач с ограничениями-равенствами и границами
    result = minimize(
        objective_function, 
        initial_weights, 
        method='SLSQP', 
        bounds=bounds, 
        constraints=constraints
    )
    
    if not result.success:
        # Если оптимизатор не сошелся, возвращаем равные веса как бэкап
        print("[Warning] Оптимизатор не смог найти решение:", result.message)
        return initial_weights
        
    return result.x
