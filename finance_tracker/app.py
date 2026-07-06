import streamlit as st
import pandas as pd
import plotly.express as px
import os

from finance_tracker.config import DB_PATH, CATEGORIES
from finance_tracker.src.storage.db_manager import (
    init_db, save_transactions, load_all_transactions, load_training_data
)
from finance_tracker.src.parser.bank_parser import parse_bank_csv
from finance_tracker.src.ml.classifier import train_classifier, prediction

# Инициализируем базу данных
init_db()

# Настройки страницы Streamlit
st.set_page_config(page_title="Умный трекер финансов", layout="wide")
st.title("💰 Личный трекер финансов с ML-категоризацией")

# 1. Боковая панель (Sidebar)
st.sidebar.header("⚙️ Управление и Загрузка")

# Блок загрузки файлов
uploaded_file = st.sidebar.file_uploader("Загрузить выписку банка (CSV)", type="csv")

# Блок переобучения модели
st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Модель машинного обучения")
if st.sidebar.button("🔄 Переобучить модель на ваших данных"):
    df_train = load_training_data()
    if len(df_train) < 5:
        st.sidebar.error("Нужно как минимум 5 размеченных транзакций в БД для обучения модели!")
    else:
        with st.sidebar.spinner("Обучаем CatBoost..."):
            train_classifier(df_train)
        st.sidebar.success("Модель успешно обучена и обновлена!")

# 2. Основная рабочая область (Вкладки)
tab_analytics, tab_upload = st.tabs(["📊 Аналитика расходов", "📥 Загрузка и Разметка"])

# ================= TAB 1: АНАЛИТИКА =================
with tab_analytics:
    df_db = load_all_transactions()
    
    if df_db.empty:
        st.info("В базе данных еще нет транзакций. Перейдите во вкладку 'Загрузка и Разметка', чтобы добавить выписку.")
    else:
        # Разделяем на расходы и доходы
        df_expenses = df_db[df_db['amount'] < 0].copy()
        df_expenses['amount'] = df_expenses['amount'].abs()  # для графиков берем модуль суммы
        df_income = df_db[df_db['amount'] >= 0].copy()
        
        total_exp = df_expenses['amount'].sum()
        total_inc = df_income['amount'].sum()
        balance = total_inc - total_exp
        
        # Виджеты ключевых показателей
        col1, col2, col3 = st.columns(3)
        col1.metric("Всего расходов", f"{total_exp:,.2f} ₽")
        col2.metric("Всего доходов", f"{total_inc:,.2f} ₽")
        col3.metric("Баланс (сбережения)", f"{balance:,.2f} ₽", delta=f"{balance:,.2f} ₽")
        
        st.markdown("---")
        
        # Визуализация расходов
        if not df_expenses.empty:
            col_chart, col_table = st.columns([2, 1])
            
            with col_chart:
                st.subheader("Распределение расходов по категориям")
                # Группируем по категориям
                df_cat = df_expenses.groupby('category', as_index=False)['amount'].sum()
                
                # Круговая диаграмма Plotly
                fig = px.pie(
                    df_cat, values='amount', names='category', 
                    color_discrete_sequence=px.colors.sequential.RdBu,
                    hole=0.4
                )
                fig.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig, use_container_width=True)
                
            with col_table:
                st.subheader("Сумма по категориям")
                # Выводим отсортированную таблицу категорий
                df_cat_sorted = df_cat.sort_values(by='amount', ascending=False).reset_index(drop=True)
                df_cat_sorted.columns = ['Категория', 'Сумма, ₽']
                st.dataframe(df_cat_sorted, use_container_width=True, hide_index=True)
                
        # Полная история транзакций
        st.markdown("---")
        st.subheader("📜 Полная история транзакций")
        st.dataframe(
            df_db[['date', 'description', 'amount', 'category']], 
            use_container_width=True, 
            hide_index=True
        )

# ================= TAB 2: ЗАГРУЗКА И РАЗМЕТКА =================
with tab_upload:
    if uploaded_file is not None:
        st.subheader("📥 Новые транзакции из выписки")
        
        # Сохраняем временный файл для парсинга
        temp_path = "temp_statement.csv"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        try:
            # Парсим выписку
            df_parsed = parse_bank_csv(temp_path)
            
            # Предсказываем категории с помощью CatBoost модели
            with st.spinner("Модель CatBoost классифицирует расходы..."):
                predicted_cats = prediction(df_parsed['description'].tolist())
            
            # Записываем предсказанные категории
            df_parsed['category'] = predicted_cats
            
            st.write(f"Успешно распознано транзакций: {len(df_parsed)}")
            st.write("Проверьте предсказанные категории. Вы можете отредактировать любую из них, нажав на нее:")
            
            # Интерактивная таблица для редактирования категорий
            edited_df = st.data_editor(
                df_parsed[['date', 'description', 'amount', 'category']],
                column_config={
                    "category": st.column_config.SelectboxColumn(
                        "Категория",
                        help="Выберите правильную категорию",
                        options=CATEGORIES,
                        required=True,
                        width="medium"
                    )
                },
                disabled=["date", "description", "amount"], # Блокируем редактирование сумм и описаний
                hide_index=True,
                use_container_width=True
            )
            
            # Кнопка сохранения в БД
            if st.button("💾 Сохранить подтвержденные транзакции в базу"):
                # Помечаем транзакции как подтвержденные человеком (is_auto=0), 
                # чтобы они стали базой для обучения модели
                edited_df['is_auto'] = 0
                
                inserted = save_transactions(edited_df)
                st.success(f"Транзакции успешно сохранены! Добавлено новых записей: {inserted}")
                # Удаляем временный файл
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
        except Exception as e:
            st.error(f"Ошибка при обработке файла: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
    else:
        st.info("Загрузите CSV-файл банковской выписки в боковом меню слева, чтобы запустить процесс разметки.")
