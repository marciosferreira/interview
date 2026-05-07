(function () {
  const _copy = {
    en: {
      btn: "Contact",
      title: "Get in Touch",
      sub: "We’ll get back to you as soon as possible.",
      name: "Your name", namePh: "Alex Johnson",
      email: "Your email", emailPh: "you@example.com",
      subject: "Subject", subjectPh: "How can we help?",
      message: "Message", messagePh: "Tell us what’s on your mind…",
      submit: "Send message", sending: "Sending…",
      success: "Message sent! We’ll be in touch soon.",
      error: "Something went wrong. Please try again.",
      errorNet: "Network error — please try again.",
    },
    pt: {
      btn: "Contato",
      title: "Entre em Contato",
      sub: "Responderemos o mais breve possível.",
      name: "Seu nome", namePh: "Alex Johnson",
      email: "Seu e-mail", emailPh: "voce@exemplo.com",
      subject: "Assunto", subjectPh: "Como podemos ajudar?",
      message: "Mensagem", messagePh: "Conte-nos o que está pensando…",
      submit: "Enviar mensagem", sending: "Enviando…",
      success: "Mensagem enviada! Entraremos em contato em breve.",
      error: "Algo deu errado. Por favor, tente novamente.",
      errorNet: "Erro de rede — por favor, tente novamente.",
    },
  };

  const lang = localStorage.getItem('preferred_lang') || 'en';
  const c = _copy[lang] || _copy.en;

  let _name = '', _email = '';
  try {
    const u = JSON.parse(localStorage.getItem('auth_user') || 'null');
    if (u) { _name = u.name || ''; _email = u.email || ''; }
  } catch (_) {}

  const style = document.createElement('style');
  style.textContent = `
    .contact-fab {
      position: fixed; bottom: 24px; right: 24px; z-index: 9000;
      background: linear-gradient(135deg, #6366f1, #7c3aed);
      color: #fff; border: none; border-radius: 50px;
      padding: 10px 18px; font-size: 13px; font-weight: 600;
      cursor: pointer; box-shadow: 0 4px 20px rgba(99,102,241,0.4);
      display: flex; align-items: center; gap: 6px;
      transition: opacity 0.2s, transform 0.2s;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .contact-fab:hover { opacity: 0.9; transform: translateY(-1px); }
    .contact-overlay {
      display: none; position: fixed; inset: 0; z-index: 9100;
      background: rgba(0,0,0,0.65); align-items: center; justify-content: center;
      padding: 24px;
    }
    .contact-overlay.open { display: flex; }
    .contact-modal {
      background: #1a1d27; border: 1px solid #2d3148; border-radius: 16px;
      padding: 32px 28px; width: 100%; max-width: 460px; position: relative;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .contact-close {
      position: absolute; top: 12px; right: 16px;
      background: none; border: none; color: #64748b;
      font-size: 24px; cursor: pointer; line-height: 1; padding: 0;
    }
    .contact-close:hover { color: #e2e8f0; }
    .contact-modal h2 { font-size: 19px; font-weight: 700; color: #f1f5f9; margin-bottom: 4px; }
    .contact-modal .c-sub { font-size: 13px; color: #64748b; margin-bottom: 20px; }
    .contact-modal label {
      display: block; font-size: 12px; font-weight: 500;
      color: #94a3b8; margin-bottom: 5px;
    }
    .contact-modal input, .contact-modal textarea {
      width: 100%; padding: 9px 12px;
      background: #0f1117; border: 1px solid #2d3148;
      border-radius: 8px; color: #f1f5f9; font-size: 13px;
      outline: none; transition: border-color 0.2s; margin-bottom: 12px;
      font-family: inherit; box-sizing: border-box;
    }
    .contact-modal input:focus, .contact-modal textarea:focus { border-color: #6366f1; }
    .contact-modal input::placeholder, .contact-modal textarea::placeholder { color: #475569; }
    .contact-modal textarea { min-height: 100px; resize: vertical; }
    .c-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .c-row > div { display: flex; flex-direction: column; }
    .c-row input { margin-bottom: 0; }
    .c-row-mb { margin-bottom: 12px; }
    .contact-submit {
      width: 100%; padding: 10px;
      background: linear-gradient(135deg, #6366f1, #7c3aed);
      border: none; border-radius: 8px; color: #fff;
      font-size: 14px; font-weight: 600; cursor: pointer;
      transition: opacity 0.2s; margin-top: 4px; font-family: inherit;
    }
    .contact-submit:hover { opacity: 0.9; }
    .contact-submit:disabled { opacity: 0.5; cursor: not-allowed; }
    .contact-result {
      font-size: 13px; border-radius: 8px; padding: 10px 12px;
      margin-bottom: 12px; display: none;
    }
    .contact-result.success { background: #052e16; border: 1px solid #166534; color: #86efac; }
    .contact-result.error   { background: #450a0a; border: 1px solid #7f1d1d; color: #fca5a5; }
  `;
  document.head.appendChild(style);

  const fab = document.createElement('button');
  fab.className = 'contact-fab';
  fab.innerHTML = '&#9993; ' + c.btn;
  document.body.appendChild(fab);

  const overlay = document.createElement('div');
  overlay.className = 'contact-overlay';
  overlay.innerHTML = `
    <div class="contact-modal">
      <button class="contact-close" id="cw-close">&times;</button>
      <h2>${c.title}</h2>
      <p class="c-sub">${c.sub}</p>
      <div class="contact-result" id="cw-result"></div>
      <form id="cw-form" autocomplete="on">
        <div class="c-row c-row-mb">
          <div>
            <label>${c.name}</label>
            <input type="text" id="cw-name" placeholder="${c.namePh}" value="${_esc(_name)}" required autocomplete="name" />
          </div>
          <div>
            <label>${c.email}</label>
            <input type="email" id="cw-email" placeholder="${c.emailPh}" value="${_esc(_email)}" required autocomplete="email" />
          </div>
        </div>
        <label>${c.subject}</label>
        <input type="text" id="cw-subject" placeholder="${c.subjectPh}" required />
        <label>${c.message}</label>
        <textarea id="cw-body" placeholder="${c.messagePh}" required></textarea>
        <button type="submit" class="contact-submit" id="cw-submit">${c.submit}</button>
      </form>
    </div>
  `;
  document.body.appendChild(overlay);

  function _esc(s) {
    return s.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  const closeModal = () => overlay.classList.remove('open');
  fab.addEventListener('click', () => overlay.classList.add('open'));
  document.getElementById('cw-close').addEventListener('click', closeModal);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

  document.getElementById('cw-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const result = document.getElementById('cw-result');
    const submit = document.getElementById('cw-submit');
    result.style.display = 'none';
    submit.disabled = true;
    submit.textContent = c.sending;

    const payload = {
      name:    document.getElementById('cw-name').value.trim(),
      email:   document.getElementById('cw-email').value.trim(),
      subject: document.getElementById('cw-subject').value.trim(),
      body:    document.getElementById('cw-body').value.trim(),
    };

    try {
      const res = await fetch('/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        result.textContent = c.success;
        result.className = 'contact-result success';
        result.style.display = 'block';
        document.getElementById('cw-subject').value = '';
        document.getElementById('cw-body').value = '';
        setTimeout(closeModal, 3000);
      } else {
        const data = await res.json().catch(() => ({}));
        result.textContent = data.detail || c.error;
        result.className = 'contact-result error';
        result.style.display = 'block';
      }
    } catch (_) {
      result.textContent = c.errorNet;
      result.className = 'contact-result error';
      result.style.display = 'block';
    } finally {
      submit.disabled = false;
      submit.textContent = c.submit;
    }
  });
})();
