HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>Limitless AI Dashboard</title>
    <style>
        :root {
            --bg-dark: #080810;
            --card-bg: #0d0d1a;
            --card-border: #1a1a2e;
            --accent: #4f9cf9;
            --accent-dim: #2d5a9e;
            --green: #00ff88;
            --red: #ff3355;
            --orange: #ff8800;
            --hold: #3a3a5c;
            --text: #e5e5e5;
            --text-dim: #8888aa;
            --text-muted: #555566;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg-dark);
            color: var(--text);
            min-height: 100vh;
            line-height: 1.5;
        }
        .container { max-width: 1600px; margin: 0 auto; padding: 20px; }
        
        .status-bar {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            gap: 40px;
            flex-wrap: wrap;
            margin-bottom: 24px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        }
        .logo {
            font-size: 1.4rem;
            font-weight: 800;
            color: var(--accent);
            letter-spacing: 2px;
            text-transform: uppercase;
        }
        .logo span { color: var(--green); }
        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.9rem;
            color: var(--text-dim);
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--text-muted);
        }
        .status-dot.online { 
            background: var(--green); 
            box-shadow: 0 0 12px var(--green); 
            animation: pulse 2s infinite;
        }
        .status-dot.offline { background: var(--red); }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        .decision-badge {
            padding: 8px 20px;
            border-radius: 6px;
            font-weight: 700;
            font-size: 1.1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .decision-badge.BUY { background: var(--green); color: #000; }
        .decision-badge.SELL { background: var(--red); color: #fff; }
        .decision-badge.HOLD { background: var(--hold); color: var(--text); }
        .decision-badge.BLOCKED { background: var(--orange); color: #000; }

        .grid {
            display: grid;
            grid-template-columns: repeat(12, 1fr);
            gap: 20px;
            margin-bottom: 24px;
        }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }
        .card-title {
            font-size: 0.75rem;
            font-weight: 600;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--card-border);
        }
        
        .col-3 { grid-column: span 3; }
        .col-4 { grid-column: span 4; }
        .col-6 { grid-column: span 6; }
        .col-8 { grid-column: span 8; }
        .col-12 { grid-column: span 12; }

        @media (max-width: 1200px) {
            .col-3 { grid-column: span 6; }
            .col-4 { grid-column: span 6; }
            .col-6 { grid-column: span 12; }
            .col-8 { grid-column: span 12; }
        }

        /* Section A: Chart */
        .chart-container {
            height: 200px;
            background: linear-gradient(180deg, rgba(79,156,249,0.05) 0%, transparent 100%);
            border-radius: 8px;
            position: relative;
            overflow: hidden;
        }
        .chart-line {
            position: absolute;
            bottom: 20px;
            left: 20px;
            right: 20px;
            height: 120px;
        }
        .chart-svg {
            width: 100%;
            height: 100%;
        }
        .chart-grid-line {
            stroke: var(--card-border);
            stroke-width: 1;
            stroke-dasharray: 4 4;
        }
        .chart-path {
            fill: none;
            stroke: var(--accent);
            stroke-width: 2;
            filter: drop-shadow(0 0 6px var(--accent));
        }
        .chart-area {
            fill: url(#chartGradient);
            opacity: 0.3;
        }
        .chart-dot {
            fill: var(--accent);
            filter: drop-shadow(0 0 8px var(--accent));
        }

        /* Section B: Last Decision */
        .decision-main {
            text-align: center;
            padding: 20px 0;
        }
        .decision-symbol {
            font-size: 3rem;
            font-weight: 800;
            margin-bottom: 8px;
        }
        .decision-action {
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 12px;
        }
        .decision-action.BUY { color: var(--green); }
        .decision-action.SELL { color: var(--red); }
        .decision-action.HOLD { color: var(--hold); }
        .decision-action.BLOCKED { color: var(--orange); }
        .decision-confidence {
            font-size: 1.2rem;
            color: var(--text-dim);
            margin-bottom: 16px;
        }
        .decision-confidence strong {
            color: var(--accent);
            font-size: 1.5rem;
        }
        .decision-meta {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid var(--card-border);
        }
        .meta-item {
            text-align: center;
        }
        .meta-label {
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .meta-value {
            font-size: 0.95rem;
            color: var(--text);
            font-weight: 600;
        }

        /* Section C: 9 Agent Cards */
        .agent-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
        }
        .agent-card {
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 14px;
            text-align: center;
            transition: all 0.3s ease;
        }
        .agent-card:hover {
            border-color: var(--accent-dim);
            background: rgba(79,156,249,0.05);
        }
        .agent-icon {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--accent-dim), var(--accent));
            margin: 0 auto 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1rem;
        }
        .agent-name {
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--text);
            margin-bottom: 4px;
        }
        .agent-score {
            font-size: 1.1rem;
            font-weight: 700;
        }
        .agent-score.positive { color: var(--green); }
        .agent-score.negative { color: var(--red); }
        .agent-score.neutral { color: var(--text-dim); }

        /* Section D: Debate */
        .debate-container {
            max-height: 280px;
            overflow-y: auto;
        }
        .debate-item {
            padding: 12px;
            margin-bottom: 10px;
            border-radius: 8px;
            border-left: 3px solid;
        }
        .debate-item.bullish {
            background: rgba(0,255,136,0.05);
            border-color: var(--green);
        }
        .debate-item.bearish {
            background: rgba(255,51,85,0.05);
            border-color: var(--red);
        }
        .debate-item.neutral {
            background: rgba(255,255,255,0.02);
            border-color: var(--text-muted);
        }
        .debate-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
        }
        .debate-agent {
            font-size: 0.8rem;
            font-weight: 600;
            color: var(--accent);
        }
        .debate-sentiment {
            font-size: 0.7rem;
            padding: 2px 8px;
            border-radius: 4px;
            text-transform: uppercase;
        }
        .debate-sentiment.bullish { background: var(--green); color: #000; }
        .debate-sentiment.bearish { background: var(--red); color: #fff; }
        .debate-sentiment.neutral { background: var(--hold); color: var(--text); }
        .debate-text {
            font-size: 0.85rem;
            color: var(--text-dim);
            line-height: 1.5;
        }

        /* Section E: Stats */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
        }
        .stat-box {
            text-align: center;
            padding: 16px;
            background: rgba(255,255,255,0.02);
            border-radius: 8px;
        }
        .stat-value {
            font-size: 1.6rem;
            font-weight: 700;
            color: var(--text);
            margin-bottom: 4px;
        }
        .stat-value.accent { color: var(--accent); }
        .stat-value.green { color: var(--green); }
        .stat-value.red { color: var(--red); }
        .stat-label {
            font-size: 0.7rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        /* Section F: Table */
        .table-container {
            overflow-x: auto;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85rem;
        }
        th {
            text-align: left;
            padding: 12px;
            background: rgba(255,255,255,0.03);
            color: var(--text-muted);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.7rem;
            letter-spacing: 1px;
            border-bottom: 1px solid var(--card-border);
        }
        td {
            padding: 12px;
            border-bottom: 1px solid var(--card-border);
            color: var(--text-dim);
        }
        tr:hover td {
            background: rgba(255,255,255,0.02);
        }
        .table-decision {
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.75rem;
            display: inline-block;
        }
        .table-decision.BUY { background: var(--green); color: #000; }
        .table-decision.SELL { background: var(--red); color: #fff; }
        .table-decision.HOLD { background: var(--hold); color: var(--text); }

        /* Section G: Polymarket */
        .polymarket-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }
        .pm-contract {
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 14px;
        }
        .pm-question {
            font-size: 0.85rem;
            color: var(--text);
            margin-bottom: 10px;
            font-weight: 500;
        }
        .pm-bars {
            display: flex;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            margin-bottom: 8px;
        }
        .pm-bar-yes {
            background: var(--green);
        }
        .pm-bar-no {
            background: var(--red);
        }
        .pm-prices {
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
        }
        .pm-yes { color: var(--green); }
        .pm-no { color: var(--red); }

        /* Section H: KB */
        .kb-list {
            max-height: 200px;
            overflow-y: auto;
        }
        .kb-item {
            display: flex;
            align-items: center;
            padding: 10px 12px;
            border-radius: 6px;
            margin-bottom: 8px;
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--card-border);
        }
        .kb-item.old {
            opacity: 0.6;
            border-color: var(--orange);
        }
        .kb-icon {
            width: 32px;
            height: 32px;
            border-radius: 6px;
            background: var(--accent-dim);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 12px;
            font-size: 0.9rem;
        }
        .kb-info {
            flex: 1;
        }
        .kb-name {
            font-size: 0.85rem;
            color: var(--text);
            margin-bottom: 2px;
        }
        .kb-meta {
            font-size: 0.7rem;
            color: var(--text-muted);
        }
        .kb-status {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        .kb-status.fresh { background: var(--green); }
        .kb-status.stale { background: var(--orange); }

        /* Section I: Health */
        .health-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 12px;
        }
        .health-item {
            text-align: center;
            padding: 16px 10px;
            background: rgba(255,255,255,0.02);
            border-radius: 8px;
            border: 1px solid var(--card-border);
        }
        .health-icon {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            margin: 0 auto 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }
        .health-icon.pass {
            background: rgba(0,255,136,0.15);
            color: var(--green);
        }
        .health-icon.fail {
            background: rgba(255,51,85,0.15);
            color: var(--red);
        }
        .health-icon.warn {
            background: rgba(255,136,0,0.15);
            color: var(--orange);
        }
        .health-label {
            font-size: 0.75rem;
            color: var(--text-dim);
        }

        /* Section J: JARVIS */
        .jarvis-container {
            background: linear-gradient(135deg, rgba(79,156,249,0.1) 0%, rgba(0,255,136,0.05) 100%);
            border: 1px solid var(--accent-dim);
            border-radius: 12px;
            padding: 24px;
            position: relative;
            overflow: hidden;
        }
        .jarvis-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, var(--accent), var(--green));
        }
        .jarvis-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
        }
        .jarvis-icon {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: linear-gradient(135deg, var(--accent), var(--green));
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            animation: glow 2s ease-in-out infinite alternate;
        }
        @keyframes glow {
            from { box-shadow: 0 0 10px var(--accent); }
            to { box-shadow: 0 0 20px var(--green); }
        }
        .jarvis-title {
            font-size: 1.3rem;
            font-weight: 700;
            color: var(--text);
        }
        .jarvis-subtitle {
            font-size: 0.8rem;
            color: var(--text-muted);
        }
        .jarvis-response {
            font-size: 0.95rem;
            color: var(--text-dim);
            line-height: 1.7;
            padding: 16px;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            max-height: 120px;
            overflow-y: auto;
        }
        .jarvis-response strong {
            color: var(--accent);
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-dark); }
        ::-webkit-scrollbar-thumb { background: var(--card-border); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
    </style>
</head>
<body>
    <div class="container">
        <!-- Status Bar -->
        <div class="status-bar">
            <div class="logo">Limitless<span>AI</span></div>
            <div class="status-item">
                <span class="status-dot {{'online' if system_online else 'offline'}}"></span>
                <span>{{'ONLINE' if system_online else 'OFFLINE'}}</span>
            </div>
            <div class="status-item">
                <span>Last run:</span>
                <strong>{{last_run_ago}}</strong>
            </div>
            <div class="status-item">
                <span>Next in:</span>
                <strong>{{next_run_in}}</strong>
            </div>
            <div class="status-item">
                <span>Spend:</span>
                <strong>${{total_spend}}</strong>
            </div>
            <div class="decision-badge {{last_decision}}">{{last_decision}}</div>
        </div>

        <!-- Sections A-F Row 1 -->
        <div class="grid">
            <!-- Section A: Chart -->
            <div class="card col-4">
                <div class="card-title">A. BTC Price Chart</div>
                <div class="chart-container">
                    <div class="chart-line">
                        <svg class="chart-svg" viewBox="0 0 400 120" preserveAspectRatio="none">
                            <defs>
                                <linearGradient id="chartGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                                    <stop offset="0%" style="stop-color:#4f9cf9;stop-opacity:0.3" />
                                    <stop offset="100%" style="stop-color:#4f9cf9;stop-opacity:0" />
                                </linearGradient>
                            </defs>
                            <line class="chart-grid-line" x1="0" y1="30" x2="400" y2="30"/>
                            <line class="chart-grid-line" x1="0" y1="60" x2="400" y2="60"/>
                            <line class="chart-grid-line" x1="0" y1="90" x2="400" y2="90"/>
                            <path class="chart-area" d="M0,100 L50,85 L100,95 L150,70 L200,60 L250,75 L300,45 L350,55 L400,30 L400,120 L0,120 Z"/>
                            <path class="chart-path" d="M0,100 L50,85 L100,95 L150,70 L200,60 L250,75 L300,45 L350,55 L400,30"/>
                            <circle class="chart-dot" cx="400" cy="30" r="4"/>
                        </svg>
                    </div>
                </div>
            </div>

            <!-- Section B: Last Decision -->
            <div class="card col-4">
                <div class="card-title">B. Last Decision</div>
                <div class="decision-main">
                    <div class="decision-symbol">₿</div>
                    <div class="decision-action {{last_decision}}">{{last_decision}}</div>
                    <div class="decision-confidence">Confidence: <strong>{{last_confidence}}%</strong></div>
                    <div class="decision-meta">
                        <div class="meta-item">
                            <div class="meta-label">Price</div>
                            <div class="meta-value">{{last_btc_price}}</div>
                        </div>
                        <div class="meta-item">
                            <div class="meta-label">Time</div>
                            <div class="meta-value">{{last_timestamp}}</div>
                        </div>
                        <div class="meta-item">
                            <div class="meta-label">Regime</div>
                            <div class="meta-value">{{last_regime}}</div>
                        </div>
                        <div class="meta-item">
                            <div class="meta-label">Miro</div>
                            <div class="meta-value">{{last_mirofish_label}}</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Section C: 9 Agent Cards -->
            <div class="card col-4">
                <div class="card-title">C. Agent Signals</div>
                <div class="agent-grid">
                    <div class="agent-card">
                        <div class="agent-icon">📊</div>
                        <div class="agent-name">Trend</div>
                        <div class="agent-score {{'positive' if last_mirofish_score > 30 else 'negative' if last_mirofish_score < -30 else 'neutral'}}">{{last_mirofish_score}}</div>
                    </div>
                    <div class="agent-card">
                        <div class="agent-icon">📈</div>
                        <div class="agent-name">Momentum</div>
                        <div class="agent-score neutral">+45</div>
                    </div>
                    <div class="agent-card">
                        <div class="agent-icon">🔗</div>
                        <div class="agent-name">On-Chain</div>
                        <div class="agent-score positive">+62</div>
                    </div>
                    <div class="agent-card">
                        <div class="agent-icon">📰</div>
                        <div class="agent-name">Sentiment</div>
                        <div class="agent-score positive">+38</div>
                    </div>
                    <div class="agent-card">
                        <div class="agent-icon">🎯</div>
                        <div class="agent-name">Options</div>
                        <div class="agent-score neutral">+12</div>
                    </div>
                    <div class="agent-card">
                        <div class="agent-icon">🌊</div>
                        <div class="agent-name">Volatility</div>
                        <div class="agent-score negative">-25</div>
                    </div>
                    <div class="agent-card">
                        <div class="agent-icon">🔍</div>
                        <div class="agent-name">Patterns</div>
                        <div class="agent-score positive">+55</div>
                    </div>
                    <div class="agent-card">
                        <div class="agent-icon">🧠</div>
                        <div class="agent-name">AI</div>
                        <div class="agent-score positive">+71</div>
                    </div>
                    <div class="agent-card">
                        <div class="agent-icon">⚡</div>
                        <div class="agent-name">Macro</div>
                        <div class="agent-score neutral">+8</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Sections D-F Row 2 -->
        <div class="grid">
            <!-- Section D: Debate -->
            <div class="card col-4">
                <div class="card-title">D. Agent Debate</div>
                <div class="debate-container">
                    <div class="debate-item bullish">
                        <div class="debate-header">
                            <span class="debate-agent">Trend Agent</span>
                            <span class="debate-sentiment bullish">BULLISH</span>
                        </div>
                        <div class="debate-text">BTC breaking above 50 EMA with strong volume. Golden cross forming on 4H.</div>
                    </div>
                    <div class="debate-item bearish">
                        <div class="debate-header">
                            <span class="debate-agent">Volatility Agent</span>
                            <span class="debate-sentiment bearish">BEARISH</span>
                        </div>
                        <div class="debate-text">IV percentile elevated. Implied volatility suggests upcoming move but direction uncertain.</div>
                    </div>
                    <div class="debate-item bullish">
                        <div class="debate-header">
                            <span class="debate-agent">On-Chain Agent</span>
                            <span class="debate-sentiment bullish">BULLISH</span>
                        </div>
                        <div class="debate-text">Exchange reserves decreasing. Long-term holder accumulation increasing.</div>
                    </div>
                    <div class="debate-item neutral">
                        <div class="debate-header">
                            <span class="debate-agent">Macro Agent</span>
                            <span class="debate-sentiment neutral">NEUTRAL</span>
                        </div>
                        <div class="debate-text">Waiting for US market open. CPI data tomorrow could shift sentiment.</div>
                    </div>
                </div>
            </div>

            <!-- Section E: Stats -->
            <div class="card col-4">
                <div class="card-title">E. Performance Stats</div>
                <div class="stats-grid">
                    <div class="stat-box">
                        <div class="stat-value">{{total_runs}}</div>
                        <div class="stat-label">Total Runs</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value accent">{{action_rate}}%</div>
                        <div class="stat-label">Action Rate</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value green">{{backtest_summary.win_rate if backtest_summary else 0}}%</div>
                        <div class="stat-label">Win Rate</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{{avg_confidence}}%</div>
                        <div class="stat-label">Avg Conf</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{{mirofish_alignment}}%</div>
                        <div class="stat-label">MF Align</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{{backtest_summary.wins if backtest_summary else 0}}</div>
                        <div class="stat-label">Wins</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">{{backtest_summary.losses if backtest_summary else 0}}</div>
                        <div class="stat-label">Losses</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">$0.043</div>
                        <div class="stat-label">Cost/Run</div>
                    </div>
                </div>
            </div>

            <!-- Section F: Table -->
            <div class="card col-4">
                <div class="card-title">F. Recent Runs</div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Time</th>
                                <th>Decision</th>
                                <th>Conf</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for run in recent_runs[:10] %}
                            <tr>
                                <td>{{run.time_ago}}</td>
                                <td><span class="table-decision {{run.decision}}">{{run.decision}}</span></td>
                                <td>{{run.confidence}}%</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Sections G-J Row 3 -->
        <div class="grid">
            <!-- Section G: Polymarket -->
            <div class="card col-4">
                <div class="card-title">G. Polymarket</div>
                <div class="polymarket-grid">
                    {% for pos in polymarket_positions[:4] %}
                    <div class="pm-contract">
                        <div class="pm-question">{{pos.question}}</div>
                        <div class="pm-bars">
                            <div class="pm-bar-yes" style="width: {{pos.yes_pct}}%"></div>
                            <div class="pm-bar-no" style="width: {{pos.no_pct}}%"></div>
                        </div>
                        <div class="pm-prices">
                            <span class="pm-yes">Yes {{pos.yes_pct}}%</span>
                            <span class="pm-no">No {{pos.no_pct}}%</span>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <!-- Section H: KB -->
            <div class="card col-4">
                <div class="card-title">H. Knowledge Base</div>
                <div class="kb-list">
                    {% for f in kb_files[:8] %}
                    <div class="kb-item {{'old' if f.is_old}}">
                        <div class="kb-icon">📄</div>
                        <div class="kb-info">
                            <div class="kb-name">{{f.name}}</div>
                            <div class="kb-meta">{{f.size}} • {{f.age}}</div>
                        </div>
                        <div class="kb-status {{'fresh' if not f.is_old else 'stale'}}"></div>
                    </div>
                    {% endfor %}
                </div>
            </div>

            <!-- Section I: Health -->
            <div class="card col-4">
                <div class="card-title">I. System Health</div>
                <div class="health-grid">
                    <div class="health-item">
                        <div class="health-icon {{'pass' if health.mirofish else 'fail'}}">🐟</div>
                        <div class="health-label">Mirofish</div>
                    </div>
                    <div class="health-item">
                        <div class="health-icon {{'pass' if health.alpaca else 'fail'}}">📊</div>
                        <div class="health-label">Alpaca</div>
                    </div>
                    <div class="health-item">
                        <div class="health-icon {{'pass' if health.openrouter else 'fail'}}">🤖</div>
                        <div class="health-label">OpenRouter</div>
                    </div>
                    <div class="health-item">
                        <div class="health-icon {{'pass' if health.cron else 'fail'}}">⏰</div>
                        <div class="health-label">Cron</div>
                    </div>
                    <div class="health-item">
                        <div class="health-icon {{'pass' if health.kb_fresh else 'warn'}}">📚</div>
                        <div class="health-label">KB</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Section J: JARVIS -->
        <div class="grid">
            <div class="card col-12">
                <div class="card-title">J. JARVIS Analysis</div>
                <div class="jarvis-container">
                    <div class="jarvis-header">
                        <div class="jarvis-icon">🤖</div>
                        <div>
                            <div class="jarvis-title">JARVIS AI Assistant</div>
                            <div class="jarvis-subtitle">Real-time market analysis and reasoning</div>
                        </div>
                    </div>
                    <div class="jarvis-response">
                        <strong>Analysis:</strong> {{last_reasoning[:500]}}
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
