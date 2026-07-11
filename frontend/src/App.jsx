import React, { useState, useEffect } from 'react';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { 
  Box, Typography, TextField, Button, Grid, CircularProgress, 
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, 
  Paper, Alert, AlertTitle, Divider, InputAdornment 
} from '@mui/material';
import { PieChart } from '@mui/x-charts/PieChart';
import { BarChart } from '@mui/x-charts/BarChart';
import { 
  TrendingUp, Percent, Calendar, AlertCircle, Save, 
  RotateCw, History, ArrowRight, Wallet 
} from 'lucide-react';

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#3b82f6' },      // Blue for TPAY
    secondary: { main: '#10b981' },    // Green for TMON
    warning: { main: '#eab308' },      // Gold for TGLD
    error: { main: '#f97316' },        // Orange/Red for BTC
    background: {
      default: '#0b0d11',
      paper: '#141a26',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", sans-serif',
  },
  components: {
    MuiTextField: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(255, 255, 255, 0.03)',
          borderRadius: 8,
        }
      }
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          textTransform: 'none',
          fontWeight: 600,
        }
      }
    }
  }
});

const ASSET_COLORS = {
  'TPAY': '#3b82f6',
  'TGLD': '#eab308',
  'BTC': '#f97316',
  'TMON': '#10b981'
};

const ASSET_NAMES_RU = {
  'TPAY': 'Облигации (TPAY)',
  'TGLD': 'Золото (TGLD)',
  'BTC': 'Биткоин (BTC)',
  'TMON': 'Ден. рынок (TMON)'
};

export default function App() {
  const [portfolioData, setPortfolioData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // holdings input form state
  const [holdings, setHoldings] = useState({ TPAY: 0, TGLD: 0, BTC: 0, TMON: 0 });
  const [savingHoldings, setSavingHoldings] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // deposit calculator state
  const [depositSum, setDepositSum] = useState("");
  const [depositResult, setDepositResult] = useState(null);

  // rebalance action state
  const [rebalancing, setRebalancing] = useState(false);
  const [rebalanceResult, setRebalanceResult] = useState(null);

  // rebalance history state
  const [history, setHistory] = useState([]);

  const fetchPortfolio = async () => {
    try {
      const res = await fetch('/api/portfolio');
      if (!res.ok) throw new Error('Не удалось загрузить данные портфеля.');
      const data = await res.json();
      setPortfolioData(data);
      setHoldings(data.holdings);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      const res = await fetch('/api/portfolio/history');
      if (res.ok) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (err) {
      console.error('Ошибка истории ребалансов:', err);
    }
  };

  useEffect(() => {
    fetchPortfolio();
    fetchHistory();
  }, []);

  // Reactive deposit calculator
  useEffect(() => {
    const amount = parseFloat(depositSum);
    if (isNaN(amount) || amount <= 0) {
      setDepositResult(null);
      return;
    }

    const delayDebounceFn = setTimeout(async () => {
      try {
        const res = await fetch('/api/portfolio/calculate-deposit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount })
        });
        if (res.ok) {
          const data = await res.json();
          setDepositResult(data);
        }
      } catch (err) {
        console.error(err);
      }
    }, 250);

    return () => clearTimeout(delayDebounceFn);
  }, [depositSum]);

  const handleSaveHoldings = async () => {
    setSavingHoldings(true);
    setSaveSuccess(false);
    try {
      const res = await fetch('/api/portfolio/holdings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ holdings })
      });
      if (res.ok) {
        const data = await res.json();
        setPortfolioData(data);
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSavingHoldings(false);
    }
  };

  const handleRebalance = async () => {
    setRebalancing(true);
    setRebalanceResult(null);
    try {
      const res = await fetch('/api/portfolio/rebalance', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setRebalanceResult(data);
        fetchPortfolio();
        fetchHistory();
      } else {
        const errData = await res.json();
        alert(`Ошибка ребалансировки: ${errData.detail || 'Внутренняя ошибка'}`);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setRebalancing(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', width: '100vw', height: '100vh', justifyContent: 'center', alignItems: 'center', bgcolor: '#0b0d11' }}>
        <CircularProgress size={60} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4, width: '100vw', height: '100vh', display: 'flex', justifyContent: 'center', alignItems: 'center', bgcolor: '#0b0d11' }}>
        <Alert severity="error" sx={{ maxWidth: 500 }}>
          <AlertTitle>Ошибка загрузки</AlertTitle>
          {error}
        </Alert>
      </Box>
    );
  }

  const {
    total_value, current_weights, target_weights, 
    last_rebalance_date, trading_days_passed, 
    rebalance_needed, rebalance_reasons, key_rate
  } = portfolioData;

  // Prepare Pie Chart Data
  const pieData = Object.keys(current_weights).map((ticker, index) => ({
    id: index,
    value: parseFloat((current_weights[ticker] * 100).toFixed(2)),
    label: `${ticker} (${(current_weights[ticker] * 100).toFixed(1)}%)`,
    color: ASSET_COLORS[ticker]
  }));

  // Prepare Bar Chart Data
  const barTickers = ['TPAY', 'TGLD', 'BTC', 'TMON'];
  const currentBarWeights = barTickers.map(t => parseFloat((current_weights[t] * 100).toFixed(1)));
  const targetBarWeights = barTickers.map(t => parseFloat((target_weights[t] * 100).toFixed(1)));

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Box className="main-layout">
        
        {/* SIDEBAR */}
        <Box className="glass-sidebar">
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
            <Wallet style={{ color: '#3b82f6', width: 28, height: 28 }} />
            <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: '-0.5px' }}>
              Ваш портфель
            </Typography>
          </Box>
          <Divider />

          {/* Asset holdings inputs */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Количество лотов / паев
            </Typography>
            {Object.keys(holdings).map(ticker => (
              <TextField
                key={ticker}
                label={ASSET_NAMES_RU[ticker]}
                type="number"
                size="small"
                value={holdings[ticker]}
                onChange={e => setHoldings({ ...holdings, [ticker]: parseFloat(e.target.value) || 0 })}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: ASSET_COLORS[ticker] }} />
                    </InputAdornment>
                  )
                }}
              />
            ))}
            
            <Button 
              variant="contained" 
              color="primary"
              onClick={handleSaveHoldings}
              disabled={savingHoldings}
              startIcon={savingHoldings ? <CircularProgress size={16} color="inherit" /> : <Save size={16} />}
              sx={{ py: 1.2 }}
            >
              Сохранить баланс
            </Button>
            {saveSuccess && (
              <Alert severity="success" sx={{ py: 0, px: 2 }}>Баланс успешно обновлен!</Alert>
            )}
          </Box>
          
          <Divider sx={{ my: 1 }} />

          {/* Deposit Calculator */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'text.secondary', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Калькулятор пополнения
            </Typography>
            <TextField
              label="Сумма пополнения"
              type="number"
              size="small"
              value={depositSum}
              onChange={e => setDepositSum(e.target.value)}
              InputProps={{
                endAdornment: <InputAdornment position="end">₽</InputAdornment>
              }}
            />

            {depositResult && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, p: 2, borderRadius: 2, bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }} className="animate-fade-in">
                <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', display: 'block', mb: 0.5 }}>
                  РЕКОМЕНДУЕМЫЕ ПОКУПКИ:
                </Typography>
                {Object.keys(depositResult).map(ticker => {
                  const item = depositResult[ticker];
                  return (
                    <Box key={ticker} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: ASSET_COLORS[ticker] }} />
                        <Typography variant="body2" sx={{ fontWeight: 600 }}>{ticker}</Typography>
                      </Box>
                      <Box sx={{ textAlign: 'right' }}>
                        <Typography variant="body2" sx={{ fontWeight: 700 }}>
                          {item.needed_lots.toFixed(t => ticker === 'BTC' ? 6 : 4)} {ticker === 'BTC' ? 'BTC' : 'паев'}
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          ~ {item.allocated_rub.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ₽
                        </Typography>
                      </Box>
                    </Box>
                  );
                })}
              </Box>
            )}
          </Box>

        </Box>

        {/* MAIN CONTENT AREA */}
        <Box className="main-content">
          
          {/* HEADER & METRIC CARDROW */}
          <Box className="animate-fade-in">
            <Typography variant="h4" sx={{ fontWeight: 800, letterSpacing: '-1px', mb: 4 }}>
              Кабинет инвестора: Управление портфелем
            </Typography>

            <Grid container spacing={3}>
              <Grid item xs={12} md={3}>
                <Box className="glass-card" sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
                  <Box sx={{ p: 1.5, borderRadius: 3, bgcolor: 'rgba(59, 130, 246, 0.1)', color: '#3b82f6' }}>
                    <TrendingUp size={24} />
                  </Box>
                  <Box>
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
                      Стоимость портфеля
                    </Typography>
                    <Typography variant="h5" sx={{ fontWeight: 800 }}>
                      {total_value.toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₽
                    </Typography>
                  </Box>
                </Box>
              </Grid>

              <Grid item xs={12} md={3}>
                <Box className="glass-card" sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
                  <Box sx={{ p: 1.5, borderRadius: 3, bgcolor: 'rgba(16, 185, 129, 0.1)', color: '#10b981' }}>
                    <Percent size={24} />
                  </Box>
                  <Box>
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
                      Ставка ЦБ РФ
                    </Typography>
                    <Typography variant="h5" sx={{ fontWeight: 800 }}>
                      {key_rate.toFixed(2)}%
                    </Typography>
                  </Box>
                </Box>
              </Grid>

              <Grid item xs={12} md={3}>
                <Box className="glass-card" sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
                  <Box sx={{ p: 1.5, borderRadius: 3, bgcolor: 'rgba(234, 179, 8, 0.1)', color: '#eab308' }}>
                    <Calendar size={24} />
                  </Box>
                  <Box>
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>
                      С прошлой ребалансировки
                    </Typography>
                    <Typography variant="h5" sx={{ fontWeight: 800 }}>
                      {trading_days_passed} торг. дн.
                    </Typography>
                  </Box>
                </Box>
              </Grid>

              <Grid item xs={12} md={3}>
                <Box className="glass-card" sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                  {rebalance_needed ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, color: '#f97316' }}>
                      <AlertCircle size={20} />
                      <Box>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700, lineHeight: 1.1 }}>
                          РЕБАЛАНСИРОВКА
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          Требуется по модели
                        </Typography>
                      </Box>
                    </Box>
                  ) : (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, color: '#10b981' }}>
                      <AlertCircle size={20} />
                      <Box>
                        <Typography variant="subtitle2" sx={{ fontWeight: 700, lineHeight: 1.1 }}>
                          ПОРТФЕЛЬ СБАЛАНСИРОВАН
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          Отклонения в пределах нормы
                        </Typography>
                      </Box>
                    </Box>
                  )}
                </Box>
              </Grid>
            </Grid>
          </Box>

          {/* Alerts for Rebalancing Reasons */}
          {rebalance_needed && (
            <Alert severity="warning" sx={{ borderRadius: 3 }} className="animate-fade-in">
              <AlertTitle sx={{ fontWeight: 700 }}>Необходима ребалансировка активов</AlertTitle>
              Система обнаружила триггерные отклонения в портфеле:
              <ul>
                {rebalance_reasons.map((reason, idx) => (
                  <li key={idx} style={{ fontWeight: 600 }}>{reason}</li>
                ))}
              </ul>
            </Alert>
          )}

          {/* CHARTS CONTAINER */}
          <Box className="animate-fade-in">
            <Grid container spacing={3}>
              <Grid item xs={12} md={5}>
                <Box className="glass-card" sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minHeight: 360 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 3, alignSelf: 'flex-start' }}>
                    Текущее распределение долей
                  </Typography>
                  <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1, width: '100%' }}>
                    {total_value > 0 ? (
                      <PieChart
                        series={[
                          {
                            data: pieData,
                            innerRadius: 75,
                            outerRadius: 110,
                            paddingAngle: 2,
                            cornerRadius: 4,
                          },
                        ]}
                        width={350}
                        height={240}
                        legend={{ hidden: true }}
                      />
                    ) : (
                      <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                        Внесите остатки, чтобы увидеть график
                      </Typography>
                    )}
                  </Box>
                </Box>
              </Grid>

              <Grid item xs={12} md={7}>
                <Box className="glass-card" sx={{ minHeight: 360, display: 'flex', flexDirection: 'column' }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
                    Текущие веса в сравнении с целевыми
                  </Typography>
                  <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', flex: 1, width: '100%', overflow: 'hidden' }}>
                    <BarChart
                      xAxis={[{ scaleType: 'band', data: barTickers }]}
                      series={[
                        { data: currentBarWeights, label: 'Текущие веса (%)', color: '#3b82f6' },
                        { data: targetBarWeights, label: 'Целевые веса (%)', color: '#10b981' }
                      ]}
                      width={520}
                      height={260}
                      legend={{ labelStyle: { fontSize: 11 } }}
                    />
                  </Box>
                </Box>
              </Grid>
            </Grid>
          </Box>

          {/* REBALANCE ACTION PANELS */}
          <Box className="glass-card animate-fade-in">
            <Typography variant="h6" sx={{ fontWeight: 700, mb: 2 }}>
              Ребалансировка портфеля по модели CatBoost + MPT
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3 }}>
              При нажатии кнопки система запустит обученные модели CatBoost для прогнозирования доходностей каждого инструмента на следующую неделю, рассчитает недельный ковариационный риск и сгенерирует оптимальные веса по модели Sortino с учетом Turnover Penalty.
            </Typography>

            <Button 
              variant="contained" 
              color="secondary"
              onClick={handleRebalance}
              disabled={rebalancing}
              startIcon={rebalancing ? <CircularProgress size={16} color="inherit" /> : <RotateCw size={16} />}
              sx={{ px: 3, py: 1.5 }}
            >
              Выполнить ребалансировку по модели
            </Button>

            {rebalanceResult && (
              <Box sx={{ mt: 4 }} className="animate-fade-in">
                <Alert severity="success" sx={{ mb: 3 }}>
                  <AlertTitle sx={{ fontWeight: 700 }}>Ребалансировка успешно рассчитана на дату {rebalanceResult.rebalance_date}!</AlertTitle>
                </Alert>

                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2, color: 'text.secondary' }}>
                        🎯 Новые целевые веса:
                      </Typography>
                      {Object.keys(rebalanceResult.target_weights).map(ticker => (
                        <Box key={ticker} sx={{ display: 'flex', justifyContent: 'space-between', mb: 1.5 }}>
                          <Typography variant="body2" sx={{ fontWeight: 600 }}>{ticker}</Typography>
                          <Typography variant="body2" sx={{ fontWeight: 700, color: '#10b981' }}>
                            {(rebalanceResult.target_weights[ticker] * 100).toFixed(2)}%
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  </Grid>

                  <Grid item xs={12} md={6}>
                    <Box sx={{ p: 2.5, borderRadius: 3, bgcolor: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 2, color: 'text.secondary' }}>
                        📋 Сделки для выполнения на бирже:
                      </Typography>
                      {rebalanceResult.recommended_trades.map((trade, idx) => (
                        <Box key={idx} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Box sx={{ 
                              px: 1, py: 0.25, borderRadius: 1.5, fontSize: 11, fontWeight: 700,
                              bgcolor: trade.action === 'КУПИТЬ' ? 'rgba(16,185,129,0.1)' : 'rgba(249,115,22,0.1)',
                              color: trade.action === 'КУПИТЬ' ? '#10b981' : '#f97316'
                            }}>
                              {trade.action}
                            </Box>
                            <Typography variant="body2" sx={{ fontWeight: 700 }}>{trade.ticker}</Typography>
                          </Box>
                          <Box sx={{ textAlign: 'right' }}>
                            <Typography variant="body2" sx={{ fontWeight: 700 }}>
                              ~ {trade.delta_lots.toFixed(trade.ticker === 'BTC' ? 6 : 4)} лотов
                            </Typography>
                            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                              на {trade.delta_rub.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ₽
                            </Typography>
                          </Box>
                        </Box>
                      ))}
                    </Box>
                  </Grid>
                </Grid>
              </Box>
            )}
          </Box>

          {/* HISTORY LOG PANEL */}
          {history.length > 0 && (
            <Box className="glass-card animate-fade-in">
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
                <History style={{ color: '#3b82f6', width: 22, height: 22 }} />
                <Typography variant="h6" sx={{ fontWeight: 700 }}>
                  История ребалансировок
                </Typography>
              </Box>

              <TableContainer component={Paper} sx={{ bgcolor: 'rgba(255,255,255,0.01)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 2 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow sx={{ bgcolor: 'rgba(255,255,255,0.02)' }}>
                      <TableCell sx={{ fontWeight: 700 }}>Дата</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>TPAY</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>TGLD</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>BTC</TableCell>
                      <TableCell align="right" sx={{ fontWeight: 700 }}>TMON</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {history.map((row, idx) => (
                      <TableRow key={idx} sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
                        <TableCell component="th" scope="row" sx={{ fontWeight: 600 }}>{row.date}</TableCell>
                        <TableCell align="right">{(row.weights.TPAY * 100).toFixed(1)}%</TableCell>
                        <TableCell align="right">{(row.weights.TGLD * 100).toFixed(1)}%</TableCell>
                        <TableCell align="right">{(row.weights.BTC * 100).toFixed(1)}%</TableCell>
                        <TableCell align="right">{(row.weights.TMON * 100).toFixed(1)}%</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          )}

        </Box>
      </Box>
    </ThemeProvider>
  );
}
