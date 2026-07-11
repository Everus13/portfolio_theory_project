import React from 'react';
import { BrainCircuit, Layers, Globe, ArrowRight } from 'lucide-react';

export default function LandingPage({ onEnterConsole }) {
  return (
    <div className="landing-container animate-in">
      
      {/* ─── NAVIGATION BAR ─── */}
      <header className="landing-header">
        <div className="landing-logo">
          <div className="landing-logo-icon">IP</div>
          <span className="landing-logo-text">INVESTOR<span>.ML</span></span>
        </div>
        <button className="btn btn-success" onClick={onEnterConsole}>
          Войти в консоль <ArrowRight size={15} />
        </button>
      </header>

      {/* ─── HERO SECTION ─── */}
      <section className="landing-hero">
        <div className="landing-hero-badge">
          <BrainCircuit size={14} style={{ color: 'var(--accent-blue)' }} />
          <span>Машинное обучение для портфелей</span>
        </div>
        <h1 className="landing-title">
          Оптимизация активов на базе <span>CatBoost</span> & <span>MPT</span>
        </h1>
        <p className="landing-subtitle">
          Управляйте вашим капиталом профессионально. Наша система использует искусственный интеллект для еженедельного прогнозирования доходности и построения оптимального защитного портфеля по методу Марковица (Sortino SLSQP).
        </p>
        <button className="landing-cta-btn" onClick={onEnterConsole}>
          Перейти в консоль <ArrowRight size={18} />
        </button>
      </section>

      {/* ─── FEATURES SECTION ─── */}
      <section className="landing-features">
        <div className="landing-features-grid">
          
          {/* Card 1 */}
          <div className="landing-card">
            <div className="landing-card-icon-wrapper" style={{ '--accent-color': 'var(--accent-blue)' }}>
              <BrainCircuit size={24} style={{ color: 'var(--accent-blue)' }} />
            </div>
            <h3 className="landing-card-title">ИИ Прогнозирование</h3>
            <p className="landing-card-text">
              CatBoost Regressor обучается на лагах доходности, индексе волатильности Мосбиржи (RVI) и динамике IMOEX для еженедельного предсказания трендов.
            </p>
          </div>

          {/* Card 2 */}
          <div className="landing-card">
            <div className="landing-card-icon-wrapper" style={{ '--accent-color': 'var(--accent-purple)' }}>
              <Layers size={24} style={{ color: 'var(--accent-purple)' }} />
            </div>
            <h3 className="landing-card-title">Оптимизатор Сортино</h3>
            <p className="landing-card-text">
              Математический алгоритм SLSQP находит оптимальные доли активов с жесткими защитными лимитами, минимизируя downside risk под безрисковую ставку ЦБ.
            </p>
          </div>

          {/* Card 3 */}
          <div className="landing-card">
            <div className="landing-card-icon-wrapper" style={{ '--accent-color': 'var(--accent-cyan)' }}>
              <Globe size={24} style={{ color: 'var(--accent-cyan)' }} />
            </div>
            <h3 className="landing-card-title">Мультивалютная Консоль</h3>
            <p className="landing-card-text">
              Оцените портфель в рублях (₽) или мгновенно переключитесь на доллары ($). Вся аналитика и расчёты пополнений адаптируются по курсу в реальном времени.
            </p>
          </div>

        </div>
      </section>

      {/* ─── FOOTER ─── */}
      <footer className="landing-footer">
        <p>© 2026 INVESTOR.ML. Все права защищены. Разработано для умного управления активами Мосбиржи и криптоактивами.</p>
      </footer>

    </div>
  );
}
