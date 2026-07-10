import sys
import os
# Добавляем корень проекта в путь импорта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import itertools
import pandas as pd
from multiprocessing import Pool
from config import DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS, TRAIN_TEST_SPLIT_DATE
from src.optimization.simulator import run_simulation

# Функция для запуска одного эксперимента (вынесена на уровень модуля для работы multiprocessing)
def run_single_experiment(params):
    depth, iterations, lr, retrain_interval, metric = params
    
    try:
        res = run_simulation(
            db_path=DB_PATH,
            tickers=PORTFOLIO_ASSETS,
            benchmarks=BENCHMARKS,
            start_date=TRAIN_TEST_SPLIT_DATE,
            depth=depth,
            iterations=iterations,
            learning_rate=lr,
            retrain_interval=retrain_interval,
            metric=metric,
            turnover_penalty_coeff=0.001,
            transaction_fee=0.001
        )
        
        if res.get('success', False):
            metrics = res['strategy_metrics']
            return {
                'depth': depth,
                'iterations': iterations,
                'learning_rate': lr,
                'retrain_interval': retrain_interval,
                'metric': metric,
                'total_return': metrics['total_return'],
                'ann_return': metrics['ann_return'],
                'ann_vol': metrics['ann_vol'],
                'sharpe': metrics['sharpe'],
                'sortino': metrics['sortino'],
                'max_dd': metrics['max_dd']
            }
    except Exception as e:
        print(f"Ошибка при тестировании параметров {params}: {e}")
    return None

def main():
    # Задаем оптимизированную сетку параметров для быстрого и репрезентативного перебора
    depths = [3, 5]
    iterations_list = [300, 600]
    lrs = [0.01, 0.05]
    
    # Интервалы переобучения (в торговых днях): 
    # None - без переобучения, 10 - 2 недели, 20 - 1 месяц, 60 - 3 месяца
    retrain_intervals = [None, 10, 20, 60]
    
    metrics = ['sharpe', 'sortino']
    
    combinations = list(itertools.product(depths, iterations_list, lrs, retrain_intervals, metrics))
    print(f"Всего комбинаций параметров для бэктеста: {len(combinations)}")
    
    # Задействуем все доступные ядра процессора для ускорения
    num_workers = os.cpu_count() or 4
    print(f"Запуск параллельных вычислений в {num_workers} процессах...")
    
    results = []
    with Pool(num_workers) as pool:
        for res in pool.imap_unordered(run_single_experiment, combinations):
            if res is not None:
                results.append(res)
                if len(results) % 20 == 0:
                    print(f"Выполнено: {len(results)}/{len(combinations)} экспериментов.")
                    
    # Сохраняем результаты в CSV
    df_results = pd.DataFrame(results)
    os.makedirs('research', exist_ok=True)
    csv_path = 'research/experiment_results.csv'
    df_results.to_csv(csv_path, index=False)
    print(f"\nВсе результаты успешно сохранены по пути: {csv_path}")
    
    # 1. Поиск лучшей модели по коэффициенту Сортино
    best_sortino = df_results.sort_values(by='sortino', ascending=False).iloc[0]
    print("\n=============================================")
    print("🏆 ЛУЧШАЯ МОДЕЛЬ ПО КОЭФФИЦИЕНТУ СОРТИНО:")
    print(f"  • CatBoost: depth={best_sortino['depth']}, iterations={best_sortino['iterations']}, lr={best_sortino['learning_rate']}")
    print(f"  • Переобучение каждые: {best_sortino['retrain_interval']} торг. дней (None - без переобучения)")
    print(f"  • Оптимизация по: {best_sortino['metric']}")
    print(f"  • Общая доходность: {best_sortino['total_return']:.2f}%")
    print(f"  • Коэффициент Сортино: {best_sortino['sortino']:.2f}")
    print(f"  • Максимальная просадка: {best_sortino['max_dd']:.2f}%")
    
    # 2. Поиск лучшей модели по коэффициенту Шарпа
    best_sharpe = df_results.sort_values(by='sharpe', ascending=False).iloc[0]
    print("\n=============================================")
    print("🏆 ЛУЧШАЯ МОДЕЛЬ ПО КОЭФФИЦИЕНТУ ШАРПА:")
    print(f"  • CatBoost: depth={best_sharpe['depth']}, iterations={best_sharpe['iterations']}, lr={best_sharpe['learning_rate']}")
    print(f"  • Переобучение каждые: {best_sharpe['retrain_interval']} торг. дней")
    print(f"  • Оптимизация по: {best_sharpe['metric']}")
    print(f"  • Общая доходность: {best_sharpe['total_return']:.2f}%")
    print(f"  • Коэффициент Шарпа: {best_sharpe['sharpe']:.2f}")
    print(f"  • Максимальная просадка: {best_sharpe['max_dd']:.2f}%")
    print("=============================================")

if __name__ == '__main__':
    main()
