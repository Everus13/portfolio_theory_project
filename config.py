import os

# Базовый путь проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Пути к директориям данных и моделей
DATA_DIR = os.path.join(BASE_DIR, 'data')
MODELS_DIR = os.path.join(BASE_DIR, 'models')
DB_PATH = os.path.join(DATA_DIR, 'portfolio.db')

# Список инструментов для портфеля
STOCKS = ['SBER', 'GAZP', 'LKOH']
FUNDS = ['TPAY', 'TGLD']
PORTFOLIO_ASSETS = STOCKS + FUNDS

# Дополнительные фичи (индекс волатильности)
BENCHMARKS = ['RVI', 'IMOEX']

# Горизонт прогнозирования для моделей (в торговых днях)
# 5 дней = приблизительно 1 торговая неделя
PREDICTION_HORIZON = 5

# Параметры оптимизации портфеля
MIN_WEIGHT = 0.05  # Минимальный вес актива (5%)
MAX_WEIGHT = 1.0   # Максимальный вес актива (100%)
LONG_ONLY = True   # Только длинные позиции (веса >= 0)

# Параметры бэктестинга
TRAIN_TEST_SPLIT_DATE = '2025-01-01'  # Пример даты начала бэктеста
