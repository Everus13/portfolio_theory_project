import os
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.metrics import mean_absolute_error, r2_score

from config import DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS, MODELS_DIR, TRAIN_TEST_SPLIT_DATE
from src.features.features_generator import build_features_and_targets

def train_models():
    # 1. Генерируем датасет с признаками
    print("Генерация признаков...")
    df = build_features_and_targets(DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS)
    
    # 2. Выделяем строки с валидным таргетом (для обучения)
    # Строки, где target равен NaN (последние 5 дней), пригодятся только для реального прогноза, их убираем.
    df_train_val = df.dropna(subset=['target']).copy()
    
    # Список признаков для обучения (исключаем технические колонки)
    feature_cols = [col for col in df_train_val.columns if col not in [
        'date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 
        'daily_return', 'rvi_close', 'imoex_close', 'target'
    ]]
    
    print(f"Используемые признаки ({len(feature_cols)}): {feature_cols}")
    
    # Папка для сохранения моделей
    os.makedirs(MODELS_DIR, exist_ok=True)
    
    # Цикл по активам
    for ticker in PORTFOLIO_ASSETS:
        print(f"\n--- Обучение модели для {ticker} ---")
        
        # Фильтруем данные по тикеру
        df_ticker = df_train_val[df_train_val['ticker'] == ticker].copy()
        if df_ticker.empty:
            print(f"Нет данных для обучения {ticker}!")
            continue
            
        # Разделяем на Train / Test по дате
        train_data = df_ticker[df_ticker['date'] < TRAIN_TEST_SPLIT_DATE]
        test_data = df_ticker[df_ticker['date'] >= TRAIN_TEST_SPLIT_DATE]
        
        if train_data.empty or test_data.empty:
            print(f"Недостаточно данных для разделения на train/test для {ticker}!")
            continue
            
        X_train, y_train = train_data[feature_cols], train_data['target']
        X_test, y_test = test_data[feature_cols], test_data['target']
        
        # 3. Инициализация и обучение CatBoost
        # Мы используем Loss-функцию RMSE. 
        # Параметр early_stopping_rounds поможет остановить обучение, если тест-метрика перестанет улучшаться.
        model = CatBoostRegressor(
            iterations=800,
            learning_rate=0.02,
            depth=5,
            loss_function='RMSE',
            random_seed=42,
            verbose=100  # Выводить логи каждые 100 итераций
        )
        
        model.fit(
            X_train, y_train,
            eval_set=(X_test, y_test),
            early_stopping_rounds=50,
            use_best_model=True
        )
        
        # 4. Оценка качества
        y_pred = model.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        print(f"Метрики для {ticker} на тест-выборке:")
        print(f"  MAE: {mae:.5f}")
        print(f"  R^2: {r2:.5f}")
        
        # 5. Сохранение модели
        model_path = os.path.join(MODELS_DIR, f"catboost_{ticker}.cbm")
        model.save_model(model_path)
        print(f"Модель сохранена по пути: {model_path}")

if __name__ == '__main__':
    train_models()
