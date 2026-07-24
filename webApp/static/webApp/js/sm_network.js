/**
 * StellarMap network toggle helpers (public ↔ testnet).
 * Pure functions — unit-testable without DOM/Vue.
 *
 * Usage (browser):
 *   StellarMapNetwork.nextState('public')
 *   // → { network_toggle: false, network_selected: 'testnet' }
 *
 * Label display is always UPPERCASE for the switch UI.
 */
(function (global) {
  'use strict';

  var PUBLIC = 'public';
  var TESTNET = 'testnet';

  function normalizeNetwork(value) {
    var v = String(value || '').trim().toLowerCase();
    if (v === TESTNET || v === 'test' || v === 'test-net') {
      return TESTNET;
    }
    return PUBLIC;
  }

  function isPublicNetwork(value) {
    return normalizeNetwork(value) === PUBLIC;
  }

  /** Map boolean toggle (true = public) → network name. */
  function networkFromToggle(isPublic) {
    return isPublic ? PUBLIC : TESTNET;
  }

  /** Map network name → boolean toggle (true = public). */
  function toggleFromNetwork(network) {
    return isPublicNetwork(network);
  }

  /**
   * Flip current network.
   * @param {string} currentNetwork 'public' | 'testnet'
   * @returns {{ network_toggle: boolean, network_selected: string, label: string }}
   */
  function nextState(currentNetwork) {
    var currentlyPublic = isPublicNetwork(currentNetwork);
    var network_toggle = !currentlyPublic;
    var network_selected = networkFromToggle(network_toggle);
    return {
      network_toggle: network_toggle,
      network_selected: network_selected,
      label: displayLabel(network_selected),
    };
  }

  /** UI label always PUBLIC / TESTNET */
  function displayLabel(network) {
    return normalizeNetwork(network).toUpperCase();
  }

  var api = {
    PUBLIC: PUBLIC,
    TESTNET: TESTNET,
    normalizeNetwork: normalizeNetwork,
    isPublicNetwork: isPublicNetwork,
    networkFromToggle: networkFromToggle,
    toggleFromNetwork: toggleFromNetwork,
    nextState: nextState,
    displayLabel: displayLabel,
  };

  global.StellarMapNetwork = api;

  /**
   * Vue mixin for pages that include search_container_include.html.
   * Required: data.network_toggle (bool) + data.network_selected ('public'|'testnet').
   * Without networkLabel / toggleNetworkSwitch, Vue render throws and #app goes blank.
   */
  global.sm_network_mixin = {
    computed: {
      networkLabel: function () {
        if (global.StellarMapNetwork) {
          return global.StellarMapNetwork.displayLabel(this.network_selected);
        }
        return String(this.network_selected || 'public').toUpperCase();
      },
    },
    methods: {
      toggleNetwork: function () {
        // Legacy path (checkbox / one-way sync from toggle → selected)
        this.network_selected = this.network_toggle ? 'public' : 'testnet';
      },
      toggleNetworkSwitch: function () {
        if (global.StellarMapNetwork) {
          var next = global.StellarMapNetwork.nextState(this.network_selected);
          this.network_toggle = next.network_toggle;
          this.network_selected = next.network_selected;
          return;
        }
        this.network_toggle = !this.network_toggle;
        this.network_selected = this.network_toggle ? 'public' : 'testnet';
      },
    },
  };

  // CommonJS for optional Node tests
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(typeof window !== 'undefined' ? window : globalThis);
