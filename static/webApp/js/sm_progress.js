/**
 * StellarMapProgress — DRY progress overlay for the whole app.
 *
 * Usage:
 *   StellarMapProgress.show({ title: 'Searching…', indeterminate: true });
 *   StellarMapProgress.set(45, 'Loading lineage…');
 *   StellarMapProgress.hide();
 *   await StellarMapProgress.wrap(fetch(...), { title: 'Loading…' });
 *   StellarMapProgress.navigate('/dashboard/', { title: 'Loading dashboard…' });
 *
 * Vue mixin (optional):
 *   mixins: [window.sm_progress_mixin]
 *   this.smProgressShow({ title: '…' }); this.smProgressHide();
 */
(function (global) {
  'use strict';

  var hideTimer = null;
  var pulseTimer = null;
  var tickTimer = null;
  var value = 0;
  var shownAt = 0;
  var baseMessage = '';

  /** Always re-query DOM (Vue remounts must not leave stale node refs). */
  function els() {
    return {
      root: document.getElementById('sm-progress'),
      bar: document.getElementById('sm-progress-bar'),
      titleEl: document.getElementById('sm-progress-title'),
      metaEl: document.getElementById('sm-progress-meta'),
    };
  }

  function clearPulse() {
    if (pulseTimer) {
      clearInterval(pulseTimer);
      pulseTimer = null;
    }
    var e = els();
    if (e.root) e.root.classList.remove('is-indeterminate');
  }

  function clearTick() {
    if (tickTimer) {
      clearInterval(tickTimer);
      tickTimer = null;
    }
  }

  function setBarWidth(pct) {
    value = Math.max(0, Math.min(100, Number(pct) || 0));
    var e = els();
    if (e.bar) e.bar.style.width = value + '%';
  }

  function elapsedSec() {
    if (!shownAt) return 0;
    return Math.max(0, (Date.now() - shownAt) / 1000);
  }

  function formatElapsed(sec) {
    if (sec < 10) return sec.toFixed(1) + 's';
    return Math.round(sec) + 's';
  }

  function updateElapsedMeta() {
    var e = els();
    if (!e.metaEl || !shownAt) return;
    var t = formatElapsed(elapsedSec());
    var msg = baseMessage ? baseMessage + ' · ' + t : t;
    e.metaEl.textContent = msg;
  }

  function startElapsedTick() {
    clearTick();
    shownAt = Date.now();
    updateElapsedMeta();
    tickTimer = setInterval(updateElapsedMeta, 200);
  }

  var Progress = {
    show: function (opts) {
      opts = opts || {};
      var e = els();
      if (!e.root) return;
      if (hideTimer) {
        clearTimeout(hideTimer);
        hideTimer = null;
      }
      e.root.hidden = false;
      e.root.removeAttribute('hidden');
      e.root.setAttribute('aria-hidden', 'false');
      e.root.setAttribute('aria-busy', 'true');
      document.body.classList.add('sm-progress-active');
      if (e.titleEl) e.titleEl.textContent = opts.title || 'Working…';
      baseMessage = opts.message || '';
      if (e.metaEl) e.metaEl.textContent = baseMessage;
      clearPulse();
      startElapsedTick();
      if (opts.indeterminate) {
        e.root.classList.add('is-indeterminate');
        setBarWidth(30);
        var dir = 1;
        pulseTimer = setInterval(function () {
          var w = value + dir * 4;
          if (w >= 90) dir = -1;
          if (w <= 20) dir = 1;
          setBarWidth(w);
        }, 120);
      } else {
        setBarWidth(opts.value != null ? opts.value : 8);
      }
    },

    set: function (pct, message) {
      var e = els();
      if (!e.root) return;
      clearPulse();
      e.root.classList.remove('is-indeterminate');
      if (message != null) {
        baseMessage = message;
      }
      if (!e.root.hidden) {
        setBarWidth(pct);
        updateElapsedMeta();
      } else {
        this.show({ value: pct, message: baseMessage });
      }
    },

    pulse: function (title, message) {
      this.show({ title: title, message: message, indeterminate: true });
    },

    /** Elapsed seconds since last show() (0 if hidden). */
    elapsed: function () {
      return elapsedSec();
    },

    hide: function (delayMs) {
      var e = els();
      if (!e.root) {
        clearTick();
        document.body.classList.remove('sm-progress-active');
        return;
      }
      clearPulse();
      setBarWidth(100);
      var sec = elapsedSec();
      if (e.metaEl && sec > 0) {
        e.metaEl.textContent = 'Loaded in ' + formatElapsed(sec);
      }
      clearTick();
      var ms = delayMs == null ? 220 : delayMs;
      if (hideTimer) clearTimeout(hideTimer);
      hideTimer = setTimeout(function () {
        var e2 = els();
        if (e2.root) {
          e2.root.hidden = true;
          e2.root.setAttribute('hidden', 'hidden');
          e2.root.setAttribute('aria-hidden', 'true');
          e2.root.setAttribute('aria-busy', 'false');
        }
        document.body.classList.remove('sm-progress-active');
        setBarWidth(0);
        if (e2.metaEl) e2.metaEl.textContent = '';
        baseMessage = '';
        shownAt = 0;
        hideTimer = null;
      }, ms);
    },

    /**
     * Wrap a promise / async function with progress UI.
     * @param {Promise|Function} work
     * @param {object} opts show() options
     */
    wrap: function (work, opts) {
      var self = this;
      opts = opts || {};
      this.show(Object.assign({ indeterminate: true }, opts));
      var p = typeof work === 'function' ? work() : work;
      return Promise.resolve(p).then(
        function (result) {
          self.set(100, opts.doneMessage || '');
          self.hide(opts.hideDelay);
          return result;
        },
        function (err) {
          var e = els();
          if (e.titleEl) e.titleEl.textContent = opts.errorTitle || 'Something went wrong';
          if (e.metaEl) e.metaEl.textContent = (err && err.message) || String(err || '');
          clearTick();
          self.hide(opts.errorHideDelay != null ? opts.errorHideDelay : 1200);
          throw err;
        }
      );
    },
  };

  global.StellarMapProgress = Progress;

  global.sm_progress_mixin = {
    methods: {
      smProgressShow: function (opts) {
        if (global.StellarMapProgress) global.StellarMapProgress.show(opts);
      },
      smProgressSet: function (pct, message) {
        if (global.StellarMapProgress) global.StellarMapProgress.set(pct, message);
      },
      smProgressPulse: function (title, message) {
        if (global.StellarMapProgress) global.StellarMapProgress.pulse(title, message);
      },
      smProgressHide: function (delayMs) {
        if (global.StellarMapProgress) global.StellarMapProgress.hide(delayMs);
      },
      smProgressWrap: function (work, opts) {
        if (global.StellarMapProgress) return global.StellarMapProgress.wrap(work, opts);
        return typeof work === 'function' ? work() : work;
      },
      /** Full-page search navigation with progress. */
      smProgressSearch: function (account, network) {
        if (global.StellarMapProgress) {
          return global.StellarMapProgress.searchAccount(account, network);
        }
        var url =
          '/search/?account=' +
          encodeURIComponent(account || '') +
          '&network=' +
          encodeURIComponent(network || 'public');
        window.location.href = url;
      },
    },
  };

  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function titleForPath(path) {
    var p = (path || '').split('?')[0];
    if (p === '/' || p === '') return 'Loading home…';
    if (p.indexOf('/search') === 0) return 'Loading search…';
    if (p.indexOf('/dashboard') === 0) return 'Loading dashboard…';
    if (p.indexOf('/high-value') >= 0) return 'Loading high value accounts…';
    if (p.indexOf('/query-builder') >= 0) return 'Loading query builder…';
    if (p.indexOf('/bulk-search') >= 0) return 'Loading bulk search…';
    if (p.indexOf('/login') === 0) return 'Loading login…';
    if (p.indexOf('/admin') === 0) return 'Loading admin…';
    return 'Loading…';
  }

  /**
   * Navigate with progress overlay that survives full page load.
   */
  Progress.navigate = function (url, opts) {
    opts = opts || {};
    var title = opts.title || titleForPath(url);
    var message = opts.message || '';
    try {
      sessionStorage.setItem('sm_progress_pending', '1');
      sessionStorage.setItem('sm_progress_title', title);
      sessionStorage.setItem('sm_progress_message', message);
      sessionStorage.setItem('sm_progress_started', String(Date.now()));
    } catch (e) { /* ignore */ }
    this.show({
      title: title,
      message: message,
      indeterminate: true,
    });
    window.location.href = url;
  };

  Progress.searchAccount = function (account, network) {
    var acct = String(account || '').trim();
    if (!acct) {
      this.show({ title: 'Enter an account', message: 'Paste a Stellar address to search.', value: 0 });
      this.hide(900);
      return;
    }
    var net = network || 'public';
    var url =
      '/search/?account=' + encodeURIComponent(acct) + '&network=' + encodeURIComponent(net);
    this.navigate(url, {
      title: 'Searching lineage…',
      message: acct,
    });
  };

  /**
   * Intercept same-origin shell links so every page nav shows progress.
   */
  Progress.bindShellNav = function () {
    if (global.__smProgressNavBound) return;
    global.__smProgressNavBound = true;

    document.addEventListener(
      'click',
      function (e) {
        if (e.defaultPrevented) return;
        if (e.button !== 0) return;
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        var a = e.target && e.target.closest ? e.target.closest('a[href]') : null;
        if (!a) return;
        // Only shell / in-app navigations
        var isShell =
          a.classList.contains('sm-nav-link') ||
          a.hasAttribute('data-sm-progress') ||
          a.classList.contains('sm-progress-nav');
        if (!isShell) return;
        if (a.getAttribute('data-sm-menu') === 'close' && (!a.getAttribute('href') || a.getAttribute('href') === '#')) {
          return;
        }
        var href = a.getAttribute('href');
        if (!href || href.charAt(0) === '#' || href.indexOf('javascript:') === 0) return;
        if (a.target === '_blank' || a.hasAttribute('download')) return;
        // External absolute URLs
        if (/^https?:\/\//i.test(href)) {
          try {
            var u = new URL(href, window.location.href);
            if (u.origin !== window.location.origin) return;
            href = u.pathname + u.search + u.hash;
          } catch (err) {
            return;
          }
        }
        e.preventDefault();
        e.stopPropagation();
        var label = (a.textContent || '').replace(/\s+/g, ' ').trim();
        Progress.navigate(href, {
          title: titleForPath(href),
          message: label,
        });
      },
      true
    );
  };

  // Full navigation: keep overlay if marked (sessionStorage) until page is ready
  try {
    if (sessionStorage.getItem('sm_progress_pending') === '1') {
      var resumeTitle = sessionStorage.getItem('sm_progress_title') || 'Loading…';
      var resumeMsg = sessionStorage.getItem('sm_progress_message') || '';
      var started = parseInt(sessionStorage.getItem('sm_progress_started') || '0', 10) || Date.now();
      sessionStorage.removeItem('sm_progress_pending');
      sessionStorage.removeItem('sm_progress_title');
      sessionStorage.removeItem('sm_progress_message');
      sessionStorage.removeItem('sm_progress_started');

      onReady(function () {
        Progress.show({
          title: resumeTitle,
          message: resumeMsg,
          indeterminate: true,
        });
        // Preserve elapsed from navigation start
        shownAt = started;
        updateElapsedMeta();

        function finish() {
          // Prefer load; fallback timeout so we never stick
          Progress.hide(280);
        }
        if (document.readyState === 'complete') {
          setTimeout(finish, 80);
        } else {
          window.addEventListener('load', function () {
            setTimeout(finish, 80);
          });
          // Safety: never leave overlay > 12s
          setTimeout(function () {
            if (document.body.classList.contains('sm-progress-active')) {
              Progress.hide(200);
            }
          }, 12000);
        }
      });
    }
  } catch (e) { /* private mode */ }

  onReady(function () {
    Progress.bindShellNav();
  });
})(typeof window !== 'undefined' ? window : this);
