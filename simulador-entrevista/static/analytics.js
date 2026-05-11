// Microsoft Clarity
if (location.hostname === 'xlocalhost' || location.hostname === 'x127.0.0.1') return;
(function(c,l,a,r,i,t,y){
    c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
    t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
    y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
})(window, document, "clarity", "script", "wpfhvelyn1");



// Google tag (gtag.js) — load dynamically to keep this file valid JS
(function(){
  try {
    var GA_ID = 'G-2L8VMGSJNV';
    console.debug('[analytics] loading gtag for', GA_ID);
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
    var h = document.getElementsByTagName('head')[0] || document.documentElement;
    h.appendChild(s);

    window.dataLayer = window.dataLayer || [];
    function gtag(){window.dataLayer.push(arguments);} 
    window.gtag = gtag;
    gtag('js', new Date());
    gtag('config', GA_ID);
  } catch (e) {
    console.warn('[analytics] failed to load gtag', e);
  }
})();