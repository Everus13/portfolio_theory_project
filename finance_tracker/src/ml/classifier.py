import os
import pandas as pd
from catboost import CatBoostClassifier
from finance_tracker.config import MODEL_PATH
from finance_tracker.src.ml.text_cleaner import clean_description

def train_classifier(df_train: pd.DataFrame) -> None:
    if df_train.empty or len(df_train['category'].unique()) < 2:
        print('недостаточно данных')
        return
        
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    df_train = df_train.copy()
    df_train['cleaned_description'] = df_train['description'].apply(clean_description)
    df_train = df_train[df_train['cleaned_description'] != '']

    x = df_train[['cleaned_description']]
    y = df_train['category']

    model = CatBoostClassifier(
        iterations=600,
        learning_rate=0.1,
        depth=4,
        loss_function='MultiClass',
        text_features=['cleaned_description'],
        random_seed=42,
        verbose=100,
        eval_metric='TotalF1',
        early_stopping_rounds=50
    )

    model.fit(x, y)
    model.save_model(MODEL_PATH)
    print(f'модель сохранена в {MODEL_PATH}')

def prediction(descriptions: list) -> list:
    if not os.path.exists(MODEL_PATH) or not descriptions:
        return ["Прочее"] * len(descriptions)
        
    cleaned_desc = [clean_description(i) for i in descriptions]
    df = pd.DataFrame({'cleaned_description': cleaned_desc})

    model = CatBoostClassifier()
    model.load_model(MODEL_PATH)

    preds = model.predict(df[['cleaned_description']])
    return [i[0] for i in preds]
