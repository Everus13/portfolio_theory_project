import React, { useState, useEffect } from 'react';
import { PieChart } from '@mui/x-charts/PieChart';
import { BarChart } from '@mui/x-charts/BarChart';
import {
  TrendingUp, Percent, Calendar, AlertTriangle, Save, RotateCw,
  History, Wallet, Calculator, Home, BarChart3, Settings,
  ChevronDown, CircleDot, ArrowUpRight, ArrowDownRight
} from 'lucide-react';

const ASSET_COLORS = {
  TPAY: '#3b82f6',
  TGLD: '#eab308',
  BTC:  '#f97316',
  TMON: '#06d6a0'
};

const ASSET_LABELS = {
  TPAY: 'Облигации',
  TGLD: 'Золото',
  BTC:  'Биткоин',
  TMON: 'Ден. рынок'
};

export default function App() {
  const [data, setData]               = useState(null);
  const [loading, setLoading]         = useState(true);
  const [holdings, setHoldings]       = useState({});
  const [saving, setSaving]           = useState(false);
  const [saved, setSaved]             = useState(false);
  const [deposit, setDeposit]         = useState('');
  const [depositRes, setDepositRes]   = useState(null);
  const [rebalancing, setRebalancing] = useState(false);
  const [rebalResult, setRebalResult] = useState(null);
  const [history, setHistory]         = useState([]);
  const [activeTab, setActiveTab]     = useState('home');

  const fetchPortfolio = async () => {
    const res = await fetch('/api/portfolio');
    const d = await res.json();
    setData(d);
    setHoldings(d.holdings);
    setLoading(false);
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch('/api/portfolio/history');
      if (res.ok) setHistory(await res.json());
    } catch {}
  };

  useEffect(() => { fetchPortfolio(); fetchHistory(); }, []);

  // Reactive deposit calculator
  useEffect(() => {
    const amt = parseFloat(deposit);
    if (isNaN(amt) || amt <= 0) { setDepositRes(null); return; }
    const t = setTimeout(async () => {
      const res = await fetch('/api/portfolio/calculate-deposit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount: amt })
      });
      if (res.ok) setDepositRes(await res.json());
    }, 200);
    return () => clearTimeout(t);
  }, [deposit]);

  const handleSave = async () => {
    setSaving(true); setSaved(false);
    const res = await fetch('/api/portfolio/holdings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ holdings })
    });
    if (res.ok) { setData(await res.json()); setSaved(true); setTimeout(() => setSaved(false), 3000); }
    setSaving(false);
  };

  const handleRebalance = async () => {
    setRebalancing(true); setRebalResult(null);
    const res = await fetch('/api/portfolio/rebalance', { method: 'POST' });
    if (res.ok) {
      setRebalResult(await res.json());
      fetchPortfolio();
      fetchHistory();
    }
    setRebalancing(false);
  };

  if (loading) return (
    <div className="loading-screen">
      <div className="spinner" />
    </div>
  );

  const { total_value, current_weights, target_weights,
    last_rebalance_date, trading_days_passed, rebalance_needed,
    rebalance_reasons, key_rate, prices } = data;

  const tickers = ['TPAY', 'TGLD', 'BTC', 'TMON'];

  const pieData = tickers.map((t, i) => ({
    id: i,
    value: +(current_weights[t] * 100).toFixed(2),
    label: `${t} ${(current_weights[t] * 100).toFixed(1)}%`,
    color: ASSET_COLORS[t]
  }));

  return (
    <div className="layout">

      {/* ─────────── SIDEBAR ─────────── */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-avatar">IP</div>
          <div>
            <div className="sidebar-user-name">Investor Panel</div>
          </div>
        </div>

        <div className="sidebar-section-label">Навигация</div>
        <nav className="sidebar-nav">
          <button className={`sidebar-item ${activeTab === 'home' ? 'active' : ''}`}
            onClick={() => setActiveTab('home')}>
            <Home size={18} /> Обзор
          </button>
          <button className={`sidebar-item ${activeTab === 'rebalance' ? 'active' : ''}`}
            onClick={() => setActiveTab('rebalance')}>
            <BarChart3 size={18} /> Ребалансировка
          </button>
          <button className={`sidebar-item ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}>
            <History size={18} /> История
          </button>
        </nav>

        <div className="sidebar-divider" />

        <div className="sidebar-section-label">Активы (лоты)</div>
        <div style={{ padding: '0 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {tickers.map(t => (
            <div className="input-group" key={t}>
              <label className="input-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: ASSET_COLORS[t], display: 'inline-block' }} />
                {t} — {ASSET_LABELS[t]}
              </label>
              <input className="input-field" type="number" step="any"
                value={holdings[t] ?? 0}
                onChange={e => setHoldings({ ...holdings, [t]: parseFloat(e.target.value) || 0 })}
              />
            </div>
          ))}
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}
            style={{ width: '100%', marginTop: 4 }}>
            <Save size={15} /> {saving ? 'Сохраняю...' : 'Сохранить баланс'}
          </button>
          {saved && <div className="alert alert-success" style={{ padding: '8px 14px', fontSize: 13 }}>Баланс обновлён!</div>}
        </div>

        <div className="sidebar-divider" />

        <div className="sidebar-section-label">Калькулятор пополнения</div>
        <div style={{ padding: '0 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="input-group">
            <label className="input-label">Сумма (₽)</label>
            <input className="input-field" type="number" placeholder="50 000"
              value={deposit} onChange={e => setDeposit(e.target.value)} />
          </div>

          {depositRes && (
            <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {tickers.map(t => {
                const r = depositRes[t];
                return (
                  <div key={t} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 13 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)' }}>
                      <span style={{ width: 6, height: 6, borderRadius: '50%', background: ASSET_COLORS[t], display: 'inline-block' }} />
                      {t}
                    </span>
                    <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                      {r.needed_lots.toFixed(t === 'BTC' ? 6 : 2)} шт
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="sidebar-footer">
          <button className="sidebar-item" style={{ opacity: 0.7 }}>
            <Settings size={18} /> Настройки
          </button>
        </div>
      </aside>

      {/* ─────────── MAIN ─────────── */}
      <main className="main-content">
        {activeTab === 'home' && <HomeTab
          total_value={total_value} current_weights={current_weights}
          target_weights={target_weights} key_rate={key_rate}
          trading_days_passed={trading_days_passed}
          rebalance_needed={rebalance_needed} rebalance_reasons={rebalance_reasons}
          pieData={pieData} tickers={tickers} prices={prices}
        />}
        {activeTab === 'rebalance' && <RebalanceTab
          rebalancing={rebalancing} handleRebalance={handleRebalance}
          rebalResult={rebalResult} tickers={tickers}
        />}
        {activeTab === 'history' && <HistoryTab history={history} />}
      </main>
    </div>
  );
}

/* ══════════════════════════════════════════════════
   HOME TAB
   ══════════════════════════════════════════════════ */
function HomeTab({ total_value, current_weights, target_weights, key_rate,
  trading_days_passed, rebalance_needed, rebalance_reasons, pieData, tickers, prices }) {
  return (
    <>
      <div className="page-header animate-in">
        <div>
          <h1 className="page-title">Dashboard Overview</h1>
          <p className="page-subtitle">Мониторинг портфеля и текущая аналитика активов</p>
        </div>
      </div>

      {/* METRIC CARDS */}
      <div className="metrics-grid stagger-children">
        <MetricCard
          icon={<TrendingUp size={18} />}
          label="Стоимость портфеля"
          value={`${total_value.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ₽`}
          badge={rebalance_needed ? null : { text: 'OK', type: 'positive' }}
        />
        <MetricCard
          icon={<Percent size={18} />}
          label="Ставка ЦБ РФ"
          value={`${key_rate.toFixed(1)}%`}
          badge={{ text: 'Ключевая', type: 'neutral' }}
        />
        <MetricCard
          icon={<Calendar size={18} />}
          label="С ребалансировки"
          value={`${trading_days_passed} дн.`}
          badge={trading_days_passed >= 20
            ? { text: 'Пора!', type: 'negative' }
            : { text: `${20 - trading_days_passed} ост.`, type: 'positive' }}
        />
        <MetricCard
          icon={<AlertTriangle size={18} />}
          label="Статус портфеля"
          value={rebalance_needed ? 'Требуется' : 'Баланс'}
          badge={rebalance_needed
            ? { text: 'Ребаланс', type: 'negative' }
            : { text: 'В норме', type: 'positive' }}
        />
      </div>

      {/* Rebalance Alert */}
      {rebalance_needed && (
        <div className="alert alert-warning animate-in">
          <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <strong>Обнаружены отклонения:</strong>
            {rebalance_reasons.map((r, i) => <div key={i} style={{ marginTop: 4 }}>• {r}</div>)}
          </div>
        </div>
      )}

      {/* CHARTS ROW */}
      <div className="content-grid animate-in">
        {/* Weights Overview (Bar Chart) */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title"><BarChart3 size={18} /> Распределение весов</div>
              <div className="card-subtitle">Текущие доли vs Целевые</div>
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', flex: 1, alignItems: 'center' }}>
            <BarChart
              xAxis={[{ scaleType: 'band', data: tickers, 
                tickLabelStyle: { fill: '#7a8ba7', fontSize: 12, fontFamily: 'Inter' } }]}
              yAxis={[{ tickLabelStyle: { fill: '#4b5e7a', fontSize: 11 } }]}
              series={[
                { data: tickers.map(t => +(current_weights[t] * 100).toFixed(1)), label: 'Текущие %', color: '#3b82f6' },
                { data: tickers.map(t => +(target_weights[t] * 100).toFixed(1)),  label: 'Целевые %', color: '#06d6a0' }
              ]}
              width={560} height={280}
              sx={{
                '.MuiChartsAxis-line': { stroke: 'rgba(255,255,255,0.06)' },
                '.MuiChartsAxis-tick': { stroke: 'rgba(255,255,255,0.06)' },
              }}
              slotProps={{ legend: { labelStyle: { fill: '#7a8ba7', fontSize: 12 } } }}
            />
          </div>
        </div>

        {/* Pie Chart */}
        <div className="card">
          <div className="card-header">
            <div className="card-title"><CircleDot size={18} /> Доли активов</div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', flex: 1, alignItems: 'center' }}>
            {total_value > 0 ? (
              <PieChart
                series={[{
                  data: pieData, innerRadius: 60, outerRadius: 100,
                  paddingAngle: 2, cornerRadius: 4,
                }]}
                width={300} height={240}
                slotProps={{ legend: { labelStyle: { fill: '#7a8ba7', fontSize: 11 } } }}
              />
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>Внесите остатки</p>
            )}
          </div>
        </div>
      </div>

      {/* PRICES TABLE */}
      <div className="card animate-in">
        <div className="card-header">
          <div className="card-title"><Wallet size={18} /> Котировки активов</div>
          <span className="card-badge">На сегодня</span>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Актив</th>
              <th>Тикер</th>
              <th>Цена (₽)</th>
              <th>Доля</th>
              <th style={{ width: 180 }}>Прогресс</th>
            </tr>
          </thead>
          <tbody>
            {tickers.map(t => (
              <tr key={t}>
                <td style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', background: ASSET_COLORS[t] }} />
                  <span style={{ fontWeight: 600 }}>{ASSET_LABELS[t]}</span>
                </td>
                <td style={{ color: 'var(--text-secondary)' }}>{t}</td>
                <td style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                  {prices[t]?.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽
                </td>
                <td>
                  <span className={`metric-badge ${current_weights[t] >= target_weights[t] ? 'positive' : 'neutral'}`}>
                    {(current_weights[t] * 100).toFixed(1)}%
                  </span>
                </td>
                <td>
                  <div className="progress-bar-container">
                    <div className="progress-bar-fill"
                      style={{ width: `${Math.min(current_weights[t] * 200, 100)}%`, background: ASSET_COLORS[t] }} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/* ══════════════════════════════════════════════════
   REBALANCE TAB
   ══════════════════════════════════════════════════ */
function RebalanceTab({ rebalancing, handleRebalance, rebalResult, tickers }) {
  return (
    <>
      <div className="page-header animate-in">
        <div>
          <h1 className="page-title">Ребалансировка портфеля</h1>
          <p className="page-subtitle">CatBoost + MPT Sortino Optimizer с Turnover Penalty</p>
        </div>
      </div>

      <div className="card animate-in">
        <div className="card-header">
          <div>
            <div className="card-title"><RotateCw size={18} /> Запуск ML-оптимизатора</div>
            <div className="card-subtitle">
              Модели прогнозируют доходность на 5 дней вперёд, затем рассчитываются веса для максимизации Sortino Ratio
            </div>
          </div>
        </div>
        <button className="btn btn-primary" onClick={handleRebalance} disabled={rebalancing}
          style={{ alignSelf: 'flex-start' }}>
          <RotateCw size={15} className={rebalancing ? 'spinning' : ''} />
          {rebalancing ? 'Расчёт...' : 'Выполнить ребалансировку'}
        </button>
      </div>

      {rebalResult && (
        <>
          <div className="alert alert-success animate-in">
            <ArrowUpRight size={18} style={{ flexShrink: 0 }} />
            <span><strong>Ребалансировка рассчитана</strong> на дату {rebalResult.rebalance_date}</span>
          </div>

          <div className="content-grid-equal animate-in">
            {/* New Weights Card */}
            <div className="card">
              <div className="card-header">
                <div className="card-title">🎯 Новые целевые веса</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {tickers.map(t => (
                  <div key={t} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 500 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: ASSET_COLORS[t] }} />
                      {t}
                    </span>
                    <span style={{ fontWeight: 800, fontSize: 16, color: 'var(--accent-cyan)' }}>
                      {(rebalResult.target_weights[t] * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Trades Card */}
            <div className="card">
              <div className="card-header">
                <div className="card-title">📋 Рекомендуемые сделки</div>
              </div>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Действие</th>
                    <th>Актив</th>
                    <th style={{ textAlign: 'right' }}>Лоты</th>
                    <th style={{ textAlign: 'right' }}>Сумма (₽)</th>
                  </tr>
                </thead>
                <tbody>
                  {rebalResult.recommended_trades.map((tr, i) => (
                    <tr key={i}>
                      <td><span className={`trade-tag ${tr.action === 'КУПИТЬ' ? 'buy' : 'sell'}`}>{tr.action}</span></td>
                      <td style={{ fontWeight: 600 }}>{tr.ticker}</td>
                      <td style={{ textAlign: 'right', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                        {tr.delta_lots.toFixed(tr.ticker === 'BTC' ? 6 : 4)}
                      </td>
                      <td style={{ textAlign: 'right', color: 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
                        {tr.delta_rub.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ₽
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  );
}

/* ══════════════════════════════════════════════════
   HISTORY TAB
   ══════════════════════════════════════════════════ */
function HistoryTab({ history }) {
  const tickers = ['TPAY', 'TGLD', 'BTC', 'TMON'];
  return (
    <>
      <div className="page-header animate-in">
        <div>
          <h1 className="page-title">История ребалансировок</h1>
          <p className="page-subtitle">Лог всех изменений целевых весов портфеля</p>
        </div>
      </div>

      <div className="card animate-in">
        {history.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', padding: 20, textAlign: 'center' }}>
            Ребалансировок ещё не проводилось
          </p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Дата</th>
                {tickers.map(t => <th key={t} style={{ textAlign: 'right' }}>{t}</th>)}
              </tr>
            </thead>
            <tbody>
              {history.map((row, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600 }}>{row.date}</td>
                  {tickers.map(t => (
                    <td key={t} style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      <span className="metric-badge neutral">
                        {(row.weights[t] * 100).toFixed(1)}%
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

/* ══════════════════════════════════════════════════
   SMALL COMPONENTS
   ══════════════════════════════════════════════════ */
function MetricCard({ icon, label, value, badge }) {
  return (
    <div className="metric-card animate-in-scale">
      <div className="metric-card-header">
        <span className="metric-card-label">{icon} {label}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <span className="metric-card-value">{value}</span>
        {badge && <span className={`metric-badge ${badge.type}`}>{badge.text}</span>}
      </div>
    </div>
  );
}
