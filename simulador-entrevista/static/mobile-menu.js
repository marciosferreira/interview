/**
 * mobile-menu.js — shared hamburger drawer for all pages.
 * Each page includes this script and provides:
 *   <button id="hamburger-btn">
 *   <div id="mobile-drawer">...</div>
 */
(function () {
  const BREAKPOINT = 768;

  function open() {
    const d = document.getElementById('mobile-drawer');
    if (d) { d.classList.add('open'); document.body.style.overflow = 'hidden'; }
  }
  function close() {
    const d = document.getElementById('mobile-drawer');
    if (d) { d.classList.remove('open'); document.body.style.overflow = ''; }
  }

  // Close on Escape
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });

  // Expose globally so inline onclick= works
  window.openMobileMenu  = open;
  window.closeMobileMenu = close;

  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('hamburger-btn');
    if (btn) btn.addEventListener('click', open);

    const backdrop = document.querySelector('#mobile-drawer .drawer-backdrop');
    if (backdrop) backdrop.addEventListener('click', close);

    const closeBtn = document.querySelector('#mobile-drawer .drawer-close');
    if (closeBtn) closeBtn.addEventListener('click', close);

    // Close drawer if resized to desktop
    window.addEventListener('resize', () => {
      if (window.innerWidth > BREAKPOINT) close();
    });
  });
})();
