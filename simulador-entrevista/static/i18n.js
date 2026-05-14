/**
 * Minimal i18n engine.
 *
 * HTML usage:
 *   data-i18n="key.path"          → sets textContent
 *   data-i18n-html="key.path"     → sets innerHTML (for keys with <span>, <br>, etc.)
 *   data-i18n-attr="attr:key"     → sets an attribute (e.g. "placeholder:key")
 *
 * JS usage:
 *   t('key.path')                 → returns translated string
 *   t('key.path', {name:'Alex'}) → with interpolation {{name}}
 */

(function () {
  const STORAGE_KEY = 'preferred_lang';
  const FALLBACK    = 'en';
  const SUPPORTED   = ['en', 'pt'];
  const CRITICAL_TRANSLATIONS = {
    en: {
      header: { tagline: 'AI-powered mock interview preparation' },
      nav: {
        homeLabel: 'Home',
        tipsLabel: 'Tips',
        signin: 'Sign in',
        getStarted: 'Get started now',
        settingsLabel: 'Settings',
        historyLabel: 'History',
        signout: 'Sign out',
        contactUs: 'Contact us',
      },
      history: {
        header: { tagline: 'Interview history' },
        nav: { newInterview: 'New interview' },
      },
      footer: {
        plans: 'Plans',
        tips: 'Interview Tips',
      },
      profile: {
        header: { tagline: 'Account settings' },
        pageHeading: 'Profile Settings',
        pageSub: 'Manage your account details and password.',
        plan: {
          currentPlan: 'Current plan',
          active: 'Active',
          free: 'Free',
          usage: '{{used}} / {{limit}} interview rounds this week',
          upgrade: 'Upgrade ->',
        },
      },
      dashboard: {
        title: "Let's prepare you for your dream job.",
        sub: 'Enter the role you want to practice for. Add job and background details if you want a more targeted interview.',
        continueTitle: 'Continue interview',
        newTitle: 'New position',
        newSub: 'Paste a job description + resume to start a personalized session',
        historyTitle: 'Interview history',
        historySub: 'Browse and continue past sessions by role',
      },
    },
    pt: {
      header: { tagline: 'Preparação para entrevistas com IA' },
      nav: {
        homeLabel: 'Início',
        tipsLabel: 'Dicas',
        signin: 'Entrar',
        getStarted: 'Começar agora',
        settingsLabel: 'Configurações',
        historyLabel: 'Histórico',
        signout: 'Sair',
        contactUs: 'Fale conosco',
      },
      history: {
        header: { tagline: 'Histórico de entrevistas' },
        nav: { newInterview: 'Nova entrevista' },
      },
      footer: {
        plans: 'Planos',
        tips: 'Dicas de Entrevista',
      },
      profile: {
        header: { tagline: 'Configurações da conta' },
        pageHeading: 'Configurações do perfil',
        pageSub: 'Gerencie os dados da sua conta e senha.',
        plan: {
          currentPlan: 'Plano atual',
          active: 'Ativo',
          free: 'Grátis',
          usage: '{{used}} / {{limit}} rounds de entrevistas essa semana',
          upgrade: 'Fazer upgrade ->',
        },
      },
      dashboard: {
        title: 'Vamos preparar você para a vaga dos seus sonhos.',
        sub: 'Informe o cargo que você quer treinar. Se quiser, adicione detalhes sobre a vaga e sobre você para criar uma entrevista mais direcionada.',
        continueTitle: 'Continuar entrevista',
        newTitle: 'Nova entrevista',
        newSub: 'Dê alguns detalhes sobre a vaga e sobre você para criar sua entrevista.',
        historyTitle: 'Histórico de entrevistas',
        historySub: 'Navegue e continue sessões anteriores por vaga',
      },
    },
  };

  function isLandingPath(path) {
    return /^\/(en|pt)?\/?$/.test(path);
  }

  function isPublicHomepagePath(path) {
    return isLandingPath(path) || (path === '/index.html' && !localStorage.getItem('auth_token'));
  }

  function detectLang() {
    // URL path takes priority: /pt → pt, /en → en (canonical landing routes)
    const seg = window.location.pathname.split('/').filter(Boolean)[0] || '';
    if (SUPPORTED.includes(seg)) return seg;
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && SUPPORTED.includes(stored)) return stored;
    // Browser detection belongs only to the landing entry point. App pages should
    // not silently change language just because the browser locale is different.
    if (!isPublicHomepagePath(window.location.pathname)) return FALLBACK;
    const browserLangs = Array.isArray(navigator.languages) && navigator.languages.length
      ? navigator.languages
      : [navigator.language || ''];
    for (const browserLang of browserLangs) {
      const lang = browserLang.slice(0, 2).toLowerCase();
      if (SUPPORTED.includes(lang)) return lang;
    }
    return FALLBACK;
  }

  let _lang = detectLang();
  // Persist so subsequent pages (register, login, etc.) inherit the same language.
  localStorage.setItem(STORAGE_KEY, _lang);
  let _dict = CRITICAL_TRANSLATIONS[_lang] || {};
  let _ready = false;
  let _readyResolve;
  const ready = new Promise(resolve => { _readyResolve = resolve; });
  if (_lang !== FALLBACK) {
    document.documentElement.classList.add('i18n-pending');
  }
  startCriticalObserver();

  function _get(obj, path) {
    return path.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), obj);
  }

  function t(key, vars) {
    let val = _get(_dict, key);
    if (val === undefined) return key;          // fallback: show the key
    if (vars) {
      val = val.replace(/\{\{(\w+)\}\}/g, (_, k) => (vars[k] !== undefined ? vars[k] : `{{${k}}}`));
    }
    return val;
  }

  function applyMetaTags() {
    const title = t('seo.title');
    const desc  = t('seo.description');
    if (title !== 'seo.title') {
      document.title = title;
      document.querySelectorAll('meta[property="og:title"], meta[name="twitter:title"]')
        .forEach(el => el.setAttribute('content', title));
    }
    if (desc !== 'seo.description') {
      document.querySelectorAll('meta[name="description"], meta[property="og:description"], meta[name="twitter:description"]')
        .forEach(el => el.setAttribute('content', desc));
    }
  }

  function _translateElement(el) {
    if (el.hasAttribute && el.hasAttribute('data-i18n')) {
      const val = t(el.dataset.i18n);
      if (val !== el.dataset.i18n) el.textContent = val;
    }
    if (el.hasAttribute && el.hasAttribute('data-i18n-html')) {
      const val = t(el.dataset.i18nHtml);
      if (val !== el.dataset.i18nHtml) el.innerHTML = val;
    }
    if (el.hasAttribute && el.hasAttribute('data-i18n-attr')) {
      const [attr, key] = el.dataset.i18nAttr.split(':');
      const val = t(key);
      if (val !== key) el.setAttribute(attr, val);
    }
  }

  function applyTranslations(opts) {
    const root = opts && opts.root ? opts.root : document;
    const finalize = !(opts && opts.finalize === false);
    if (root.querySelectorAll) {
      root.querySelectorAll('[data-i18n], [data-i18n-html], [data-i18n-attr]').forEach(_translateElement);
    }
    if (root !== document) _translateElement(root);
    if (!finalize) return;
    applyMetaTags();
    // Update <html lang>
    document.documentElement.lang = _lang;
    document.documentElement.classList.remove('i18n-pending');
    // Update switcher buttons
    document.querySelectorAll('.lang-btn').forEach(btn => {
      btn.classList.toggle('lang-active', btn.dataset.lang === _lang);
    });
  }

  function startCriticalObserver() {
    if (!window.MutationObserver) return;
    const observer = new MutationObserver(mutations => {
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType === 1) applyTranslations({ root: node, finalize: false });
        });
      });
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    document.addEventListener('i18n:ready', () => observer.disconnect(), { once: true });
  }

  async function loadLang(lang) {
    try {
      const res = await fetch(`/locales/${lang}.json?v=6`);
      if (!res.ok) throw new Error(res.status);
      _dict = await res.json();
      _lang = lang;
      localStorage.setItem(STORAGE_KEY, lang);
      document.cookie = `${STORAGE_KEY}=${lang}; path=/; max-age=${365 * 24 * 3600}; samesite=lax`;
      applyTranslations();
      // Notify app code that translations are ready
      _ready = true;
      _readyResolve();
      document.dispatchEvent(new CustomEvent('i18n:ready', { detail: { lang } }));
    } catch (e) {
      console.warn('[i18n] Failed to load', lang, e);
      if (lang !== FALLBACK) loadLang(FALLBACK);
    }
  }

  function switchLang(lang) {
    if (!SUPPORTED.includes(lang) || lang === _lang) return;
    const onLanding = isLandingPath(window.location.pathname);
    if (onLanding) history.replaceState(null, '', `/${lang}/`);
    _dict = CRITICAL_TRANSLATIONS[lang] || {};
    _lang = lang;
    localStorage.setItem(STORAGE_KEY, lang);
    document.cookie = `${STORAGE_KEY}=${lang}; path=/; max-age=${365 * 24 * 3600}; samesite=lax`;
    applyTranslations({ finalize: false });
    loadLang(lang);
  }

  // Public API
  window.t          = t;
  window.i18n       = { switchLang, currentLang: () => _lang, ready, isReady: () => _ready };

  // Boot — redirect root to language-specific URL
  if (window.location.pathname === '/' || (window.location.pathname === '/index.html' && !localStorage.getItem('auth_token'))) {
    window.location.replace('/' + _lang + '/');
  } else {
    loadLang(_lang);
  }
})();
