from config import DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS
from src.storage.db_manager import init_db
from src.parser.moex_client import update_database

def main():
    print("Инициализация базы данных...")
    init_db(DB_PATH)
    
    print("\nЗапуск обновления котировок активов...")
    for ticker in PORTFOLIO_ASSETS:
        update_database(DB_PATH, ticker, is_index=False)
        
    print("\nЗапуск обновления котировок индексов...")
    for benchmark in BENCHMARKS:
        update_database(DB_PATH, benchmark, is_index=True)
        
    print("\nВсе данные успешно обновлены!")

if __name__ == '__main__':
    main()
