(function () {
  // Google Analytics
  var GA_ID = 'G-2L8VMGSJNV';

  // Meta/Facebook Pixel
  var META_PIXEL_ID = '922838040801171';

  // Google Analytics setup
  window.dataLayer = window.dataLayer || [];
  window.gtag = window.gtag || function () {
    window.dataLayer.push(arguments);
  };

  window.gtag('js', new Date());

  var script = document.createElement('script');
  script.async = true;
  script.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(GA_ID);
  document.head.appendChild(script);

  window.gtag('config', GA_ID);

  // Meta/Facebook Pixel setup
  if (!window.fbq) {
    var fbq = window.fbq = function () {
      if (fbq.callMethod) {
        fbq.callMethod.apply(fbq, arguments);
      } else {
        fbq.queue.push(arguments);
      }
    };

    if (!window._fbq) {
      window._fbq = fbq;
    }

    fbq.push = fbq;
    fbq.loaded = true;
    fbq.version = '2.0';
    fbq.queue = [];

    var metaScript = document.createElement('script');
    metaScript.async = true;
    metaScript.src = 'https://connect.facebook.net/en_US/fbevents.js';
    document.head.appendChild(metaScript);
  }

  window.fbq('init', META_PIXEL_ID);
  window.fbq('track', 'PageView');

  // LinkedIn Ads
  var LI_PARTNER_ID = '9139274';
  window._linkedin_data_partner_ids = window._linkedin_data_partner_ids || [];
  window._linkedin_data_partner_ids.push(LI_PARTNER_ID);
  if (!window.lintrk) {
    window.lintrk = function(a, b) { window.lintrk.q.push([a, b]); };
    window.lintrk.q = [];
  }
  var liScript = document.createElement('script');
  liScript.type = 'text/javascript';
  liScript.async = true;
  liScript.src = 'https://snap.licdn.com/li.lms-analytics/insight.min.js';
  document.head.appendChild(liScript);
})();


