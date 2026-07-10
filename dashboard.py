import os
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

from config import (
    DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS, MODELS_DIR, ASSET_BOUNDS,
    REBALANCE_THRESHOLD
)
from src.storage.db_manager import (
    get_connection, get_last_date, get_last_key_rate, save_prices
)
from src.features.features_generator import build_features_and_targets
from src.optimization.optimization import optimize_portfolio
from daily_check import (
    PORTFOLIO_STATE_FILE, load_user_holdings, get_last_rebalance_info,
    save_rebalance_event, update_all_data
)
from catboost import CatBoostRegressor

# Настройка темы страницы
st.set_page_config(page_title="Инвестор-Дашборд", layout="wide", page_icon="📈")

# Стилизация под Sleek Dark Mode / Vibrant Glassmorphism
st.markdown("""
    <style>
        .reportview-container {
            background: #0e1117;
        }
        .stMetric {
            background-color: #1f2937;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #374151;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        .stAlert {
            border-radius: 10px;
        }
        div[data-testid="stExpander"] {
            border-radius: 10px;
            border: 1px solid #374151;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📈 Кабинет инвестора: Управление портфелем")

# Инициализируем БД и статус, если нужно
update_all_data()

# 1. Загрузка цен и состояния портфеля
holdings = load_user_holdings()

current_prices = {}
last_prices_date = None
for ticker in PORTFOLIO_ASSETS:
    last_prices_date = get_last_date(DB_PATH, ticker)
    query = "SELECT close FROM asset_prices WHERE ticker = ? ORDER BY date DESC LIMIT 1"
    with get_connection(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (ticker,))
        row = cursor.fetchone()
        current_prices[ticker] = row[0] if row else 1.0

# 2. Боковая панель для ввода активов инвестора (Количество паев)
st.sidebar.header("💼 Ваши активы (лоты/паи)")
new_holdings = {}
for t in PORTFOLIO_ASSETS:
    # Описание актива
    desc = ""
    if t == 'TPAY': desc = " (Облигации)"
    elif t == 'TGLD': desc = " (Золото)"
    elif t == 'TMON': desc = " (Ден. рынок)"
    elif t == 'BTC': desc = " (Биткоин)"
    
    val = st.sidebar.number_input(
        f"{t}{desc}", 
        min_value=0.0, 
        value=float(holdings.get(t, 0.0)), 
        format="%.4f"
    )
    new_holdings[t] = val

# Кнопка сохранения баланса
if st.sidebar.button("💾 Сохранить изменения баланса"):
    with open(PORTFOLIO_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_holdings, f, indent=4)
    st.sidebar.success("Остатки портфеля сохранены!")
    st.rerun()

# 3. Расчет текущих показателей
portfolio_values = {t: new_holdings[t] * current_prices[t] for t in PORTFOLIO_ASSETS}
total_val = sum(portfolio_values.values())

st.subheader(f"📊 Сводная аналитика портфеля (Цены от {last_prices_date})")

if total_val <= 0:
    st.warning("Пожалуйста, введите количество ваших лотов/паев в боковом меню слева, чтобы отобразить дашборд.")
else:
    # Считаем текущие веса
    current_weights = {t: portfolio_values[t] / total_val for t in PORTFOLIO_ASSETS}
    
    # Считаем показатели
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Стоимость портфеля", f"{total_val:,.2f} ₽")
    with col2:
        st.metric("Доля Облигаций (TPAY)", f"{current_weights['TPAY']*100:.1f}%")
    with col3:
        st.metric("Доля Золота (TGLD)", f"{current_weights['TGLD']*100:.1f}%")
    with col4:
        st.metric("Доля Биткоина (BTC)", f"{current_weights['BTC']*100:.1f}%")
        
    st.markdown("---")
    
    # 4. Проверка необходимости ребалансировки
    last_rebalance_date, target_weights = get_last_rebalance_info()
    
    # Количество торговых дней с прошлой ребалансировки
    query = "SELECT COUNT(DISTINCT date) FROM asset_prices WHERE ticker = 'TMON' AND date > ?"
    with get_connection(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (last_rebalance_date,))
        row = cursor.fetchone()
        trading_days_passed = row[0] if row else 0
        
    # Проверка отклонений весов
    time_trigger = (trading_days_passed >= 20)
    drift_trigger = False
    max_drift_ticker = None
    max_drift_val = 0.0
    for t in PORTFOLIO_ASSETS:
        drift = abs(current_weights[t] - target_weights.get(t, 0.25))
        if drift > max_drift_val:
            max_drift_val = drift
            max_drift_ticker = t
        if drift > REBALANCE_THRESHOLD:
            drift_trigger = True
            
    rebalance_needed = time_trigger or drift_trigger
    
    col_trigger, col_info = st.columns([1, 2])
    with col_trigger:
        st.subheader("🛎️ Статус ребаланса")
        if rebalance_needed:
            st.error("🚨 ТРЕБУЕТСЯ РЕБАЛАНСИРОВКА!")
            causes = []
            if time_trigger: causes.append("прошло более 20 торговых дней")
            if drift_trigger: causes.append(f"отклонение {max_drift_ticker} составило {max_drift_val*100:.2f}% (порог 5%)")
            st.write(f"Причина: {', '.join(causes)}.")
        else:
            st.success("✅ Портфель сбалансирован")
            st.write(f"Макс. отклонение: {max_drift_ticker} ({max_drift_val*100:.2f}%). Календарных дней до ребаланса: {20 - trading_days_passed} торг. дн.")
            
    with col_info:
        st.subheader("📅 Информация")
        st.write(f"• Последняя ребалансировка была: **{last_rebalance_date}**")
        st.write(f"• Прошло торговых дней с момента ребаланса: **{trading_days_passed}**")
        st.write(f"• Безрисковая ставка ЦБ РФ: **{get_last_key_rate(DB_PATH, last_prices_date):.2f}%**")
        
    st.markdown("---")
    
    # 5. Отрисовка графиков Plotly (Текущие веса vs Целевые)
    col_pie, col_bar = st.columns(2)
    
    with col_pie:
        st.subheader("Текущие доли активов")
        fig_pie = go.Figure(data=[go.Pie(
            labels=PORTFOLIO_ASSETS,
            values=[portfolio_values[t] for t in PORTFOLIO_ASSETS],
            hole=.4,
            marker=dict(colors=['#3b82f6', '#f59e0b', '#ef4444', '#10b981'])
        )])
        fig_pie.update_layout(template="plotly_dark", height=350, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with col_bar:
        st.subheader("Текущие веса в сравнении с целевыми")
        fig_bar = go.Figure(data=[
            go.Bar(name='Текущие веса', x=PORTFOLIO_ASSETS, y=[current_weights[t]*100 for t in PORTFOLIO_ASSETS], marker_color='#3b82f6'),
            go.Bar(name='Целевые веса', x=PORTFOLIO_ASSETS, y=[target_weights.get(t, 0.25)*100 for t in PORTFOLIO_ASSETS], marker_color='#10b981')
        ])
        fig_bar.update_layout(barmode='group', template="plotly_dark", height=350, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig_bar, use_container_width=True)
        
    st.markdown("---")
    
    # 6. Кнопка расчета/запуска новой ребалансировки
    st.subheader("⚙️ Симуляция ребалансировки по модели")
    
    if st.button("🔄 Выполнить ребалансировку по лучшим параметрам"):
        with st.spinner("Рассчитываем новые оптимальные веса..."):
            # Лучшие параметры по результатам grid search тестов (защитный портфель)
            depth = 5
            iterations = 300
            lr = 0.01
            metric = 'sortino'
            
            # Генерация фичей
            df_feat = build_features_and_targets(DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS)
            df_feat = df_feat[df_feat['date'] == last_prices_date].copy()
            
            feature_cols = [col for col in df_feat.columns if col not in [
                'date', 'ticker', 'open', 'high', 'low', 'close', 'volume', 
                'daily_return', 'rvi_close', 'imoex_close', 'target'
            ]]
            
            # Получение предсказаний моделей
            predictions = []
            for t in PORTFOLIO_ASSETS:
                model_path = os.path.join(MODELS_DIR, f"catboost_{t}.cbm")
                if not os.path.exists(model_path):
                    # Если моделей нет, обучаем
                    df_train = build_features_and_targets(DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS)
                    df_train_sub = df_train[(df_train['ticker'] == t) & df_train['target'].notna()]
                    model = CatBoostRegressor(iterations=iterations, depth=depth, learning_rate=lr, loss_function='RMSE', random_seed=42, verbose=0)
                    model.fit(df_train_sub[feature_cols], df_train_sub['target'])
                    model.save_model(model_path)
                
                model = CatBoostRegressor()
                model.load_model(model_path)
                row_feat = df_feat[df_feat['ticker'] == t]
                pred = model.predict(row_feat[feature_cols])[0] if not row_feat.empty else 0.0
                predictions.append(pred)
            predictions = np.array(predictions)
            
            # Получение ковариации
            df_all_prices = build_features_and_targets(DB_PATH, PORTFOLIO_ASSETS, BENCHMARKS)
            df_all_prices['daily_return'] = df_all_prices.groupby('ticker')['close'].pct_change()
            all_dates_list = sorted(df_all_prices['date'].unique())
            idx_all = all_dates_list.index(last_prices_date)
            past_dates = all_dates_list[max(0, idx_all - 60):idx_all]
            df_past = df_all_prices[df_all_prices['date'].isin(past_dates)]
            df_pivot = df_past.pivot(index='date', columns='ticker', values='daily_return')
            df_pivot = df_pivot[PORTFOLIO_ASSETS].fillna(0.0)
            
            cov_matrix_5d = df_pivot.cov().values * 5
            historical_returns_matrix = df_pivot.values
            
            # Ставка ЦБ
            risk_free_rate = get_last_key_rate(DB_PATH, last_prices_date) / 100.0
            
            # Оптимизатор
            current_w_array = np.array([current_weights[t] for t in PORTFOLIO_ASSETS])
            new_w_array = optimize_portfolio(
                tickers=PORTFOLIO_ASSETS,
                expected_returns=predictions,
                cov_matrix=cov_matrix_5d,
                historical_returns=historical_returns_matrix,
                risk_free_rate=risk_free_rate,
                metric=metric,
                previous_weights=current_w_array,
                turnover_penalty_coeff=0.001
            )
            
            new_weights_dict = dict(zip(PORTFOLIO_ASSETS, new_w_array))
            
            # Выводим веса и сделки
            st.success("Ребалансировка успешно рассчитана!")
            
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                st.markdown("### 🎯 Новые веса:")
                for t in PORTFOLIO_ASSETS:
                    st.write(f"**{t}**: {new_weights_dict[t]*100:.2f}% (было: {current_weights[t]*100:.2f}%)")
                    
            with col_res2:
                st.markdown("### 📋 Сделки для выполнения:")
                for t in PORTFOLIO_ASSETS:
                    target_val = total_val * new_weights_dict[t]
                    current_val = portfolio_values[t]
                    delta_val = target_val - current_val
                    delta_lots = delta_val / current_prices[t]
                    
                    action = "🛒 КУПИТЬ" if delta_lots > 0 else "🛑 ПРОДАТЬ"
                    st.write(f"**{action} {t}** на сумму **{abs(delta_val):,.2f} ₽** (~ {abs(delta_lots):,.4f} лотов/паев)")
                    
            # Сохраняем событие в историю
            save_rebalance_event(last_prices_date, new_weights_dict)
            st.info("Событие ребалансировки записано в историю базы данных.")
            
    # Выводим историю ребалансировок
    st.markdown("---")
    with st.expander("📜 Просмотреть историю ребалансировок в базе данных"):
        query = "SELECT date, target_weights_json FROM portfolio_status ORDER BY date DESC"
        with get_connection(DB_PATH) as conn:
            df_status = pd.read_sql_query(query, conn)
        if not df_status.empty:
            st.dataframe(df_status, use_container_width=True, hide_index=True)
        else:
            st.write("История ребалансировок пока пуста.")
