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

  let _dict = {};
  let _lang = detectLang();

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

  function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const val = t(el.dataset.i18n);
      if (val !== el.dataset.i18n) el.textContent = val;
    });
    document.querySelectorAll('[data-i18n-html]').forEach(el => {
      const val = t(el.dataset.i18nHtml);
      if (val !== el.dataset.i18nHtml) el.innerHTML = val;
    });
    document.querySelectorAll('[data-i18n-attr]').forEach(el => {
      const [attr, key] = el.dataset.i18nAttr.split(':');
      const val = t(key);
      if (val !== key) el.setAttribute(attr, val);
    });
    applyMetaTags();
    // Update <html lang>
    document.documentElement.lang = _lang;
    // Update switcher buttons
    document.querySelectorAll('.lang-btn').forEach(btn => {
      btn.classList.toggle('lang-active', btn.dataset.lang === _lang);
    });
  }

  async function loadLang(lang) {
    try {
      const res = await fetch(`/locales/${lang}.json?v=4`);
      if (!res.ok) throw new Error(res.status);
      _dict = await res.json();
      _lang = lang;
      localStorage.setItem(STORAGE_KEY, lang);
      document.cookie = `${STORAGE_KEY}=${lang}; path=/; max-age=${365 * 24 * 3600}; samesite=lax`;
      applyTranslations();
      // Notify app code that translations are ready
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
    loadLang(lang);
  }

  // Public API
  window.t          = t;
  window.i18n       = { switchLang, currentLang: () => _lang };

  // Boot — redirect root to language-specific URL
  if (window.location.pathname === '/' || (window.location.pathname === '/index.html' && !localStorage.getItem('auth_token'))) {
    window.location.replace('/' + _lang + '/');
  } else {
    loadLang(_lang);
  }
})();
