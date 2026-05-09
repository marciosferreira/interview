import re

with open(r"c:\Users\mnsmferr\interview\simulador-entrevista\static\interview.html", "r", encoding="utf-8") as f:
    content = f.read()

# Replace <style> block and imports in head
new_head_content = """  <!-- Fonts & Icons -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/lucide@latest"></script>

  <!-- Styles -->
  <link rel="stylesheet" href="/css/main.css">
  <link rel="stylesheet" href="/css/components.css">
  <link rel="stylesheet" href="/css/layout.css">
  
  <style>
    body {
      background: var(--bg-base);
      color: var(--text-primary);
      height: 100dvh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    #status-badge {
      margin-left: auto;
      font-size: 11px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: var(--radius-pill);
      background: var(--bg-surface-border);
      color: var(--text-secondary);
      transition: all 0.3s;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    #status-badge.connected   { background: var(--status-success-bg); color: var(--status-success); border: 1px solid var(--status-success-border); }
    #status-badge.recording   { background: var(--status-error-bg); color: var(--status-error); border: 1px solid var(--status-error-border); }
    #status-badge.processing  { background: rgba(99, 102, 241, 0.1); color: var(--brand-primary); border: 1px solid rgba(99, 102, 241, 0.2); }
    
    #home-btn, #new-btn, #history-btn {
      margin-left: 8px;
      font-size: 12px; font-weight: 600;
      padding: 6px 12px; border-radius: var(--radius-md);
      background: transparent; border: 1px solid var(--bg-surface-border);
      color: var(--text-secondary); cursor: pointer; transition: all 0.2s;
      text-decoration: none; display: inline-flex; align-items: center; gap: 6px;
    }
    #home-btn:hover, #history-btn:hover { border-color: var(--brand-primary); color: var(--brand-primary); background: rgba(99, 102, 241, 0.05); }
    #new-btn:hover { background: var(--brand-primary); color: white; border-color: var(--brand-primary); }
    
    #tips-btn-hdr, #profile-btn-hdr {
      font-size: 12px; font-weight: 600; padding: 6px 12px; border-radius: var(--radius-md);
      background: transparent; border: 1px solid var(--bg-surface-border); color: var(--text-secondary);
      text-decoration: none; transition: all 0.2s; display: inline-flex; align-items: center; gap: 6px; margin-left: 8px;
    }
    #tips-btn-hdr:hover, #profile-btn-hdr:hover { border-color: var(--brand-primary); color: var(--brand-primary); background: rgba(99, 102, 241, 0.05); }

    /* ── Mobile drawer ── */
    #mobile-drawer { display: none; position: fixed; inset: 0; z-index: 8000; }
    #mobile-drawer.open { display: block; }
    .drawer-backdrop { position: absolute; inset: 0; background: rgba(0,0,0,0.6); backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px); }
    .drawer-panel {
      position: absolute; top: 0; right: 0; bottom: 0; width: min(300px, 85vw);
      background: var(--bg-surface); border-left: 1px solid var(--bg-surface-border);
      display: flex; flex-direction: column; padding: 20px; gap: 8px; overflow-y: auto;
      animation: slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    @keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
    .drawer-header { display: flex; align-items: center; justify-content: space-between; padding-bottom: 16px; margin-bottom: 8px; border-bottom: 1px solid var(--bg-surface-border); }
    .drawer-header span { font-size: 16px; font-weight: 600; color: var(--text-primary); }
    .drawer-close { background: transparent; border: none; color: var(--text-secondary); cursor: pointer; padding: 4px; display: flex; align-items: center; justify-content: center; }
    .drawer-item {
      display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: var(--radius-md);
      font-size: 14px; font-weight: 500; color: var(--text-secondary); text-decoration: none; background: transparent;
      border: none; cursor: pointer; width: 100%; text-align: left; transition: all 0.2s;
    }
    .drawer-item:hover { background: rgba(99, 102, 241, 0.1); color: var(--brand-primary); }
    .drawer-item i { width: 18px; height: 18px; flex-shrink: 0; }
    .drawer-divider { height: 1px; background: var(--bg-surface-border); margin: 8px 0; }

    /* ── Mobile header ── */
    #phase-mobile-label { display: none; }
    @media (max-width: 768px) {
      .app-header { padding: 12px 16px; gap: 8px; }
      .header-brand-info { display: none; }
      .badge { display: none !important; }
      #status-badge { margin-left: auto; }
      #profile-btn-hdr, #tips-btn-hdr, #history-btn, #new-btn-wrap { display: none; }
      /* Phase bar: dots only */
      .ps-label { display: none; }
      .phase-connector { min-width: 4px; max-width: 16px; }
      #phase-bar { padding: 0 16px; }
      #phase-mobile-label {
        display: block; text-align: center; font-size: 12px; font-weight: 600;
        color: var(--brand-primary); padding: 8px 16px; background: var(--bg-surface);
        border-bottom: 1px solid var(--bg-surface-border); letter-spacing: 0.03em;
      }
      #input-area { padding: 12px 16px; }
    }

    /* ── New-interview popover ── */
    #new-popover {
      display: none; position: absolute; top: calc(100% + 8px); right: 0;
      background: var(--bg-surface); border: 1px solid var(--bg-surface-border);
      border-radius: var(--radius-lg); padding: 8px; z-index: 600; min-width: 260px;
      box-shadow: 0 10px 30px -10px rgba(0,0,0,0.5);
    }
    #new-popover.open { display: block; animation: fadeIn 0.2s; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }
    .pop-item {
      display: flex; align-items: flex-start; gap: 12px; padding: 12px;
      border-radius: var(--radius-md); cursor: pointer; transition: background 0.2s;
    }
    .pop-item:hover { background: rgba(99, 102, 241, 0.1); }
    .pop-item-icon { flex-shrink: 0; margin-top: 2px; color: var(--brand-primary); }
    .pop-item-text strong { display: block; font-size: 14px; color: var(--text-primary); margin-bottom: 2px; }
    .pop-item-text span   { font-size: 12px; color: var(--text-secondary); line-height: 1.4; }
    #new-btn-wrap { position: relative; display: inline-flex; margin-left: 8px; }

    /* ── Phase progress bar ── */
    #phase-bar {
      background: var(--bg-surface); border-bottom: 1px solid var(--bg-surface-border);
      padding: 0 24px; flex-shrink: 0; overflow-x: auto; scrollbar-width: none;
    }
    #phase-bar::-webkit-scrollbar { display: none; }
    .phase-steps { display: flex; align-items: center; max-width: 860px; margin: 0 auto; height: 48px; }
    .phase-step { display: flex; align-items: center; gap: 8px; flex-shrink: 0; cursor: default; }
    .phase-step .ps-dot {
      width: 8px; height: 8px; border-radius: 50%; background: var(--bg-surface-border);
      transition: all 0.3s; flex-shrink: 0;
    }
    .phase-step .ps-label {
      font-size: 11px; color: var(--text-secondary); font-weight: 500;
      letter-spacing: 0.05em; text-transform: uppercase; transition: color 0.3s; white-space: nowrap;
    }
    .phase-step.active .ps-dot  { background: var(--brand-primary); box-shadow: 0 0 10px rgba(99, 102, 241, 0.5); }
    .phase-step.active .ps-label { color: var(--brand-primary); font-weight: 700; }
    .phase-step.done   .ps-dot  { background: var(--status-success); }
    .phase-step.done   .ps-label { color: var(--status-success); }
    .phase-connector {
      flex: 1; height: 2px; min-width: 12px; max-width: 48px; background: var(--bg-surface-border);
      transition: background 0.3s; flex-shrink: 1; margin: 0 4px; border-radius: 1px;
    }
    .phase-connector.done { background: var(--status-success); }

    /* ── Chat area ── */
    #chat {
      flex: 1; overflow-y: auto; padding: 32px 24px;
      display: flex; flex-direction: column; gap: 24px;
    }
    #chat::-webkit-scrollbar { width: 6px; }
    #chat::-webkit-scrollbar-track { background: transparent; }
    #chat::-webkit-scrollbar-thumb { background: var(--bg-surface-border); border-radius: 3px; }

    .bubble-row { display: flex; gap: 16px; max-width: 860px; width: 100%; margin: 0 auto; }
    .bubble-row.ai       { align-self: flex-start; }
    .bubble-row.user     { align-self: flex-end; flex-direction: row-reverse; }
    .bubble-row.feedback { align-self: center; width: 100%; max-width: 900px; }

    .avatar {
      width: 36px; height: 36px; border-radius: 12px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 700;
    }
    .avatar.ai   { background: var(--brand-gradient); color: #fff; box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3); }
    .avatar.user { background: var(--bg-surface-border); color: var(--text-primary); border: 1px solid rgba(255,255,255,0.1); }

    .bubble {
      padding: 16px 20px; border-radius: var(--radius-lg); font-size: 15px; line-height: 1.6;
      max-width: 100%; overflow-wrap: break-word; word-break: break-word; min-width: 0;
    }
    .bubble-row.ai   .bubble { background: var(--bg-surface); border: 1px solid var(--bg-surface-border); border-top-left-radius: 4px; color: var(--text-primary); }
    .bubble-row.user .bubble { background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.2); border-top-right-radius: 4px; color: var(--text-primary); }

    .replay-btn {
      display: inline-flex; align-items: center; gap: 6px; margin-top: 8px; padding: 4px 10px;
      background: transparent; border: 1px solid var(--bg-surface-border); border-radius: var(--radius-sm);
      color: var(--text-secondary); font-size: 12px; font-weight: 500; cursor: pointer; transition: all 0.2s;
    }
    .replay-btn:hover { color: var(--brand-primary); border-color: var(--brand-primary); background: rgba(99, 102, 241, 0.1); }
    .replay-btn.user  { border-color: rgba(99, 102, 241, 0.3); color: var(--text-secondary); }
    .replay-btn.user:hover { color: var(--brand-primary); border-color: var(--brand-primary); }

    /* Markdown rendering inside bubbles */
    .bubble p, .feedback-card p { margin: 0 0 12px 0; }
    .bubble p:last-child, .feedback-card p:last-child { margin-bottom: 0; }
    .bubble strong, .feedback-card strong { color: var(--text-primary); font-weight: 600; }
    .bubble em, .feedback-card em { color: var(--text-secondary); font-style: italic; }
    .bubble ul, .bubble ol, .feedback-card ul, .feedback-card ol { margin: 8px 0 8px 20px; padding: 0; }
    .bubble li, .feedback-card li { margin-bottom: 6px; }
    .bubble hr, .feedback-card hr { border: none; border-top: 1px solid var(--bg-surface-border); margin: 16px 0; }
    .bubble h1, .bubble h2, .bubble h3, .feedback-card h1, .feedback-card h2, .feedback-card h3 { color: var(--brand-primary); margin: 16px 0 8px 0; font-size: 16px; font-weight: 700; }
    .bubble code, .feedback-card code { background: rgba(0,0,0,0.3); border-radius: 4px; padding: 2px 6px; font-size: 13px; color: #7dd3fc; }

    /* Feedback card */
    .feedback-card {
      background: rgba(168, 85, 247, 0.05); border: 1px solid rgba(168, 85, 247, 0.2);
      border-radius: var(--radius-xl); padding: 28px; width: 100%;
    }
    .feedback-card { font-size: 15px; line-height: 1.6; color: var(--text-primary); }

    /* Typing indicator */
    .typing-indicator {
      display: flex; align-items: center; gap: 6px; padding: 16px 20px;
      background: var(--bg-surface); border: 1px solid var(--bg-surface-border);
      border-radius: var(--radius-lg); border-top-left-radius: 4px; width: fit-content;
    }
    .typing-indicator span {
      width: 8px; height: 8px; background: var(--brand-primary); border-radius: 50%;
      animation: bounce 1.2s infinite; opacity: 0.5;
    }
    .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
    .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes bounce { 0%, 60%, 100% { transform: translateY(0); opacity: .5; } 30% { transform: translateY(-6px); opacity: 1; } }

    /* ── Input area ── */
    #input-area { padding: 24px; background: var(--bg-surface); border-top: 1px solid var(--bg-surface-border); flex-shrink: 0; box-shadow: 0 -10px 30px rgba(0,0,0,0.2); }
    #input-row { display: flex; gap: 12px; align-items: flex-end; max-width: 860px; margin: 0 auto; }
    #text-input {
      flex: 1; background: var(--bg-base); border: 1px solid var(--bg-surface-border);
      border-radius: var(--radius-lg); padding: 14px 18px; color: var(--text-primary);
      font-size: 15px; resize: none; outline: none; min-height: 52px; max-height: 160px;
      transition: all 0.2s; line-height: 1.5; box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
    }
    #text-input:focus { border-color: var(--brand-primary); box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2), inset 0 2px 4px rgba(0,0,0,0.1); }
    #text-input:disabled { opacity: 0.5; cursor: not-allowed; }
    #text-input::placeholder { color: var(--text-tertiary); }

    .icon-btn {
      width: 52px; height: 52px; border: none; border-radius: var(--radius-md);
      cursor: pointer; display: flex; align-items: center; justify-content: center;
      flex-shrink: 0; font-size: 20px; transition: all 0.2s;
    }
    #mic-btn { background: rgba(99, 102, 241, 0.1); color: var(--brand-primary); border: 1px solid rgba(99, 102, 241, 0.2); }
    #mic-btn:hover { background: var(--brand-primary); color: white; }
    #mic-btn.active { background: var(--status-error); color: white; animation: pulse 1.5s infinite; border-color: var(--status-error); }
    #mic-btn:disabled { opacity: 0.3; cursor: not-allowed; animation: none; }

    #send-btn { background: var(--brand-gradient); color: #fff; box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3); }
    #send-btn:hover { opacity: 0.9; transform: translateY(-1px); }
    #send-btn:disabled { opacity: 0.3; cursor: not-allowed; transform: none; box-shadow: none; }

    /* ── TTS bar ── */
    #tts-player {
      display: none; flex-shrink: 0; align-items: center; justify-content: center; gap: 12px;
      background: var(--bg-surface); border-bottom: 1px solid var(--bg-surface-border); padding: 10px 24px;
      animation: tts-fadein 0.2s ease;
    }
    @keyframes tts-fadein { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }
    #tts-label { font-size: 13px; font-weight: 600; color: var(--brand-primary); white-space: nowrap; display: flex; align-items: center; gap: 8px; }
    #tts-label .tts-dot {
      display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--brand-primary);
      animation: tts-pulse 1.2s ease-in-out infinite;
    }
    @keyframes tts-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; transform: scale(0.8); } }
    #pause-btn, #skip-btn {
      background: transparent; border: 1px solid var(--bg-surface-border); color: var(--text-secondary);
      border-radius: var(--radius-pill); font-size: 13px; font-weight: 600; padding: 6px 16px;
      cursor: pointer; transition: all 0.2s; white-space: nowrap; display: flex; align-items: center; gap: 6px;
    }
    #pause-btn:hover, #skip-btn:hover { background: var(--bg-surface-border); color: var(--text-primary); }

    #cancel-rec-btn { background: var(--status-error-bg); color: var(--status-error); border: 1px solid var(--status-error-border); display: none; }
    #cancel-rec-btn:hover { background: var(--status-error); color: white; }

    /* ── Audio preview bar ── */
    #audio-preview { display: none; align-items: center; gap: 16px; max-width: 860px; margin: 0 auto; background: var(--bg-base); padding: 12px 20px; border-radius: var(--radius-lg); border: 1px solid var(--bg-surface-border); }
    #ap-play {
      width: 44px; height: 44px; border-radius: 50%; background: var(--brand-primary); color: #fff;
      border: none; cursor: pointer; flex-shrink: 0; display: flex; align-items: center; justify-content: center;
      transition: all 0.2s; box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3);
    }
    #ap-play:hover { opacity: 0.9; transform: scale(1.05); }
    #ap-track { flex: 1; display: flex; flex-direction: column; gap: 6px; }
    #ap-progress {
      width: 100%; height: 6px; border-radius: 3px; background: var(--bg-surface-border); appearance: none;
      cursor: pointer; accent-color: var(--brand-primary); outline: none;
    }
    #ap-times { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-secondary); font-weight: 500; }
    #ap-discard { background: transparent; color: var(--status-error); border: 1px solid var(--status-error-border); border-radius: var(--radius-sm); padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; transition: all 0.2s; display: flex; align-items: center; gap: 6px; }
    #ap-discard:hover { background: var(--status-error-bg); }
    #ap-send { background: var(--brand-primary); color: #fff; border: none; border-radius: var(--radius-sm); padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; transition: all 0.2s; display: flex; align-items: center; gap: 6px; box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3); }
    #ap-send:hover { opacity: 0.9; transform: translateY(-1px); }

    @keyframes pulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,.4); } 50% { box-shadow: 0 0 0 10px rgba(239,68,68,0); } }

    #hint { font-size: 12px; color: var(--text-tertiary); text-align: center; margin-top: 16px; }

    /* Done banner */
    #done-banner {
      display: none; text-align: center; padding: 14px; background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2);
      color: var(--status-success); font-size: 14px; font-weight: 600; border-radius: var(--radius-md); margin-bottom: 16px;
      transition: all 0.2s;
    }
    #done-banner:hover { background: rgba(16, 185, 129, 0.15); }

  /* ── Scorecard panel ── */
  #scorecard-panel { padding: 16px 24px 40px; }
  #scorecard-panel .sc-inner {
    max-width: 860px; margin: 0 auto; background: var(--bg-surface); border: 1px solid var(--brand-primary);
    border-radius: var(--radius-xl); padding: 32px 40px; box-shadow: 0 20px 40px -10px rgba(99, 102, 241, 0.15);
  }
  #scorecard-panel .sc-inner h1, #scorecard-panel .sc-inner h2, #scorecard-panel .sc-inner h3 { color: var(--brand-secondary); margin: 24px 0 12px; font-size: 16px; font-weight: 700; }
  #scorecard-panel .sc-inner h1 { font-size: 20px; color: var(--text-primary); margin-top: 0; }
  #scorecard-panel .sc-inner p  { font-size: 15px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 16px; }
  #scorecard-panel .sc-inner strong { color: var(--text-primary); }
  #scorecard-panel .sc-inner ul, #scorecard-panel .sc-inner ol { padding-left: 24px; margin-bottom: 16px; }
  #scorecard-panel .sc-inner li { font-size: 15px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 8px; }
  #scorecard-panel .sc-inner hr { border: none; border-top: 1px solid var(--bg-surface-border); margin: 24px 0; }
  #scorecard-panel .sc-loading { text-align: center; color: var(--text-tertiary); font-size: 14px; padding: 40px; display: flex; flex-direction: column; align-items: center; gap: 16px; }
  </style>"""

new_header_drawer = """<header class="app-header">
  <a class="header-brand-link" href="/">
    <div class="header-logo"><i data-lucide="target" style="width: 22px; height: 22px;"></i></div>
    <div class="header-brand-info">
      <h1>Acing Interviews</h1>
      <p id="header-subtitle">Connecting...</p>
    </div>
  </a>
  <div id="status-badge"><i data-lucide="loader" class="spinner" style="width:14px;height:14px"></i> Connecting...</div>
  <span id="plan-pill" class="badge"></span>
  <div class="header-actions">
    <a id="profile-btn-hdr" href="/profile.html" title="Account settings"><i data-lucide="settings" style="width:16px;height:16px"></i> Settings</a>
    <a id="tips-btn-hdr" href="/tips.html" title="Interview tips & frameworks"><i data-lucide="lightbulb" style="width:16px;height:16px"></i> Tips</a>
    <a id="history-btn" href="/history.html" title="View all past interviews"><i data-lucide="clipboard-list" style="width:16px;height:16px"></i> History</a>
    <div id="new-btn-wrap">
      <button id="new-btn" title="Start a new interview"><i data-lucide="plus" style="width:16px;height:16px"></i> New</button>
      <div id="new-popover">
        <div class="pop-item" id="pop-same-role">
          <div class="pop-item-icon"><i data-lucide="refresh-cw" style="width:18px;height:18px"></i></div>
          <div class="pop-item-text">
            <strong data-i18n="interview.popover.sameRole">New round — same role</strong>
            <span data-i18n="interview.popover.sameRoleSub">Practice again with the same job & resume</span>
          </div>
        </div>
        <div class="pop-item" id="pop-new-role">
          <div class="pop-item-icon"><i data-lucide="file-edit" style="width:18px;height:18px"></i></div>
          <div class="pop-item-text">
            <strong data-i18n="interview.popover.newRole">New role</strong>
            <span data-i18n="interview.popover.newRoleSub">Enter a different job description & resume</span>
          </div>
        </div>
      </div>
    </div>
  </div>
  <button class="mobile-menu-btn" id="hamburger-btn" aria-label="Menu"><i data-lucide="menu"></i></button>
</header>

<!-- Mobile drawer -->
<div id="mobile-drawer">
  <div class="drawer-backdrop"></div>
  <nav class="drawer-panel">
    <div class="drawer-header">
      <span>Menu</span>
      <button class="drawer-close"><i data-lucide="x"></i></button>
    </div>
    <a class="drawer-item" href="/"><i data-lucide="home"></i> <span data-i18n="nav.homeLabel">Home</span></a>
    <a class="drawer-item" href="/profile.html"><i data-lucide="settings"></i> <span data-i18n="nav.settingsLabel">Settings</span></a>
    <a class="drawer-item" href="/tips.html"><i data-lucide="lightbulb"></i> <span data-i18n="nav.tipsLabel">Tips</span></a>
    <a class="drawer-item" href="/history.html"><i data-lucide="clipboard-list"></i> <span data-i18n="history.nav.current">History</span></a>
    <div class="drawer-divider"></div>
    <button class="drawer-item" id="drawer-new-same"><i data-lucide="refresh-cw"></i> <span data-i18n="interview.popover.sameRole">New round — same role</span></button>
    <button class="drawer-item" id="drawer-new-role"><i data-lucide="file-edit"></i> <span data-i18n="interview.popover.newRole">New role</span></button>
    <div class="drawer-divider"></div>
    <button class="drawer-item" onclick="closeMobileMenu(); window.openContactWidget?.()"><i data-lucide="mail"></i> Contact us</button>
  </nav>
</div>"""

content = re.sub(r'<style>.*?</style>', new_head_content, content, flags=re.DOTALL)
content = re.sub(r'<header>.*?</header>\s*<!-- Mobile drawer -->\s*<div id="mobile-drawer">.*?</div>', new_header_drawer, content, flags=re.DOTALL)

# Status updates inside JS
content = content.replace("badge.textContent = 'Connected';", "badge.innerHTML = '<i data-lucide=\"check-circle\" style=\"width:14px;height:14px\"></i> Connected'; lucide.createIcons();")
content = content.replace("badge.textContent = 'Ready to send';", "badge.innerHTML = '<i data-lucide=\"send\" style=\"width:14px;height:14px\"></i> Ready to send'; lucide.createIcons();")
content = content.replace("badge.textContent = 'Transcribing…';", "badge.innerHTML = '<i data-lucide=\"loader\" class=\"spinner\" style=\"width:14px;height:14px\"></i> Transcribing...'; lucide.createIcons();")
content = content.replace("badge.textContent = 'Processing…';", "badge.innerHTML = '<i data-lucide=\"loader\" class=\"spinner\" style=\"width:14px;height:14px\"></i> Processing...'; lucide.createIcons();")
content = content.replace("badge.textContent = 'Error';", "badge.innerHTML = '<i data-lucide=\"alert-triangle\" style=\"width:14px;height:14px\"></i> Error'; lucide.createIcons();")
content = content.replace("badge.textContent = 'Done';", "badge.innerHTML = '<i data-lucide=\"check-circle\" style=\"width:14px;height:14px\"></i> Done'; lucide.createIcons();")
content = content.replace("badge.textContent = 'Reconnecting…';", "badge.innerHTML = '<i data-lucide=\"refresh-cw\" class=\"spinner\" style=\"width:14px;height:14px\"></i> Reconnecting...'; lucide.createIcons();")
content = content.replace("badge.textContent = `🔴 ${mm}:${ss}`;", "badge.innerHTML = `<i data-lucide=\"mic\" style=\"width:14px;height:14px\"></i> ${mm}:${ss}`; lucide.createIcons();")

# JS bubble replay button
content = content.replace("btn.innerHTML = '🔊 replay';", "btn.innerHTML = '<i data-lucide=\"volume-2\" style=\"width:14px;height:14px\"></i> replay';")
content = content.replace("document.getElementById('sc-tts-btn').addEventListener", "lucide.createIcons();\n          document.getElementById('sc-tts-btn').addEventListener")

# JS scorecard html
content = content.replace('🔊 ${t(\'interview.scorecard.readAloud\')}', '<i data-lucide=\"volume-2\" style=\"width:14px;height:14px\"></i> ${t(\'interview.scorecard.readAloud\')}')

# JS TTS
content = content.replace("pauseBtn.textContent = '⏸ Pause';", "pauseBtn.innerHTML = '<i data-lucide=\"pause\" style=\"width:14px;height:14px\"></i> Pause'; lucide.createIcons();")
content = content.replace("pauseBtn.textContent = t('interview.tts.pause');", "pauseBtn.innerHTML = '<i data-lucide=\"pause\" style=\"width:14px;height:14px\"></i> ' + t('interview.tts.pause'); lucide.createIcons();")
content = content.replace("pauseBtn.textContent = t('interview.tts.resume');", "pauseBtn.innerHTML = '<i data-lucide=\"play\" style=\"width:14px;height:14px\"></i> ' + t('interview.tts.resume'); lucide.createIcons();")

# JS audio preview play icon
content = content.replace("apPlay.textContent = '▶';", "apPlay.innerHTML = '<i data-lucide=\"play\" style=\"width:20px;height:20px\"></i>'; lucide.createIcons();")
content = content.replace("apPlay.textContent = '⏸';", "apPlay.innerHTML = '<i data-lucide=\"pause\" style=\"width:20px;height:20px\"></i>'; lucide.createIcons();")

# HTML hints and buttons
content = content.replace("Click <strong>🎙️</strong> to start/stop recording", "Click <strong><i data-lucide=\"mic\" style=\"width:14px;height:14px;vertical-align:middle\"></i></strong> to start/stop recording")

content = content.replace('<button id="pause-btn" title="Pause / Resume audio"><i data-lucide="pause" style="width:14px;height:14px"></i> <span data-i18n="interview.tts.pause">Pause</span></button>', '<button id="pause-btn" title="Pause / Resume audio"><i data-lucide="pause" style="width:14px;height:14px"></i> <span data-i18n="interview.tts.pause">Pause</span></button>')
content = content.replace('<button id="skip-btn" title="Skip audio"><i data-lucide="skip-forward" style="width:14px;height:14px"></i> <span data-i18n="interview.tts.skip">Skip</span></button>', '<button id="skip-btn" title="Skip audio"><i data-lucide="skip-forward" style="width:14px;height:14px"></i> <span data-i18n="interview.tts.skip">Skip</span></button>')

content = content.replace('<button id="mic-btn" class="icon-btn" disabled title="Click to start/stop recording"><i data-lucide="mic"></i></button>', '<button id="mic-btn" class="icon-btn" disabled title="Click to start/stop recording"><i data-lucide="mic"></i></button>')
content = content.replace('<button id="cancel-rec-btn" class="icon-btn" title="Cancel recording"><i data-lucide="x"></i></button>', '<button id="cancel-rec-btn" class="icon-btn" title="Cancel recording"><i data-lucide="x"></i></button>')
content = content.replace('<button id="send-btn" class="icon-btn" disabled title="Send (Enter)"><i data-lucide="send"></i></button>', '<button id="send-btn" class="icon-btn" disabled title="Send (Enter)"><i data-lucide="send"></i></button>')

content = content.replace('<button id="ap-play" title="Play / Pause"><i data-lucide="play" style="width:20px;height:20px"></i></button>', '<button id="ap-play" title="Play / Pause"><i data-lucide="play" style="width:20px;height:20px"></i></button>')
content = content.replace('<button id="ap-discard"><i data-lucide="x" style="width:14px;height:14px"></i> <span data-i18n="interview.audio.discard">Discard</span></button>', '<button id="ap-discard"><i data-lucide="x" style="width:14px;height:14px"></i> <span data-i18n="interview.audio.discard">Discard</span></button>')
content = content.replace('<button id="ap-send"><i data-lucide="send" style="width:14px;height:14px"></i> <span data-i18n="interview.audio.send">Send</span></button>', '<button id="ap-send"><i data-lucide="send" style="width:14px;height:14px"></i> <span data-i18n="interview.audio.send">Send</span></button>')

content = content.replace("</script>\n<script src=\"/mobile-menu.js\">", "  lucide.createIcons();\n</script>\n<script src=\"/mobile-menu.js\">")

# Scorecard loading
content = content.replace("`<div class=\"sc-loading\">${t('interview.scorecard.loading')}</div>`", "`<div class=\"sc-loading\"><span class=\"spinner\" style=\"width:32px;height:32px;border-width:3px;border-top-color:var(--brand-primary);\"></span>${t('interview.scorecard.loading')}</div>`")

# Scorecard emoji removal
content = content.replace("<div style=\"font-size:28px;margin-bottom:12px\">📄</div>", "<div style=\"margin-bottom:16px;color:var(--brand-primary)\"><i data-lucide=\"file-text\" style=\"width:48px;height:48px\"></i></div>")

# Plan pill
content = content.replace("el.className = 'plan-pill ' + (isHunter ? 'hunter' : 'explorer');", "el.className = 'badge ' + (isHunter ? 'badge-primary' : '');\n    if(!isHunter) { el.style.border = '1px solid var(--bg-surface-border)'; el.style.color = 'var(--text-secondary)'; }")
content = content.replace("el.textContent = isHunter ? '🎯 Hunter' : '🗺️ Explorer';", "el.innerHTML = isHunter ? '<i data-lucide=\"target\" style=\"width:12px;height:12px;margin-right:4px\"></i> Hunter' : '<i data-lucide=\"map\" style=\"width:12px;height:12px;margin-right:4px\"></i> Explorer';\n    lucide.createIcons();")

with open(r"c:\Users\mnsmferr\interview\simulador-entrevista\static\interview.html", "w", encoding="utf-8") as f:
    f.write(content)
