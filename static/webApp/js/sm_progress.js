/**
 * StellarMapProgress — DRY progress overlay for the whole app.
 *
 * Usage:
 *   StellarMapProgress.show({ title: 'Searching…', indeterminate: true });
 *   StellarMapProgress.set(45, 'Loading lineage…');
 *   StellarMapProgress.hide();
 *   await StellarMapProgress.wrap(fetch(...), { title: 'Loading…' });
 *
 * Vue mixin (optional):
 *   mixins: [window.sm_progress_mixin]
 *   this.smProgressShow({ title: '…' }); this.smProgressHide();
 */
(function (global) {
  'use strict';

  var hideTimer = null;
  var pulseTimer = null;
  var value = 0;

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

  function setBarWidth(pct) {
    value = Math.max(0, Math.min(100, Number(pct) || 0));
    var e = els();
    if (e.bar) e.bar.style.width = value + '%';
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
      if (e.metaEl) e.metaEl.textContent = opts.message || '';
      clearPulse();
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
      if (!e.root.hidden) {
        setBarWidth(pct);
        if (message != null && e.metaEl) e.metaEl.textContent = message;
      } else {
        this.show({ value: pct, message: message });
      }
    },

    pulse: function (title, message) {
      this.show({ title: title, message: message, indeterminate: true });
    },

    hide: function (delayMs) {
      var e = els();
      if (!e.root) {
        document.body.classList.remove('sm-progress-active');
        return;
      }
      clearPulse();
      setBarWidth(100);
      var ms = delayMs == null ? 180 : delayMs;
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
          if (titleEl) titleEl.textContent = opts.errorTitle || 'Something went wrong';
          if (metaEl) metaEl.textContent = (err && err.message) || String(err || '');
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
    },
  };

  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  // Full navigation: keep overlay if marked (sessionStorage) until next page paints
  try {
    if (sessionStorage.getItem('sm_progress_pending') === '1') {
      onReady(function () {
        Progress.show({
          title: sessionStorage.getItem('sm_progress_title') || 'Loading…',
          message: sessionStorage.getItem('sm_progress_message') || '',
          indeterminate: true,
        });
        sessionStorage.removeItem('sm_progress_pending');
        sessionStorage.removeItem('sm_progress_title');
        sessionStorage.removeItem('sm_progress_message');
        // Hide shortly after load so content is usable
        setTimeout(function () {
          Progress.hide(200);
        }, 450);
      });
    }
  } catch (e) { /* private mode */ }

  /**
   * Navigate with progress overlay that survives full page load.
   */
  Progress.navigate = function (url, opts) {
    opts = opts || {};
    try {
      sessionStorage.setItem('sm_progress_pending', '1');
      sessionStorage.setItem('sm_progress_title', opts.title || 'Loading…');
      sessionStorage.setItem('sm_progress_message', opts.message || '');
    } catch (e) { /* ignore */ }
    this.show({
      title: opts.title || 'Loading…',
      message: opts.message || '',
      indeterminate: true,
    });
    window.location.href = url;
  };
})(typeof window !== 'undefined' ? window : this);
