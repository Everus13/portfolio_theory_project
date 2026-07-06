import os

# Базовый путь проекта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Пути к файлам и папкам
DATA_DIR = os.path.join(BASE_DIR, 'data')
MODELS_DIR = os.path.join(BASE_DIR, 'models')
DB_PATH = os.path.join(DATA_DIR, 'finance.db')
MODEL_PATH = os.path.join(MODELS_DIR, 'catboost_finance_classifier.cbm')

# Дефолтный список категорий для трат и доходов
CATEGORIES = [
    "Продукты и супермаркеты",
    "Транспорт и такси",
    "Кафе и рестораны",
    "Здоровье и аптеки",
    "Коммунальные платежи и связь",
    "Одежда и обувь",
    "Дом и ремонт",
    "Развлечения и хобби",
    "Переводы и платежи",
    "Прочее",
    "Доход (Зарплата / Переводы)"
]

# Карта колонок для парсинга выписки (по умолчанию Т-Банк)
BANK_COLUMNS_MAP = {
    'Дата операции': 'date',
    'Описание': 'description',
    'Сумма операции': 'amount',
    'Категория': 'category'
}
