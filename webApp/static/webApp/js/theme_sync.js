/*
 * theme_sync.js
 * Real-time theme synchronization across tabs/windows
 * Listens for theme changes in localStorage and applies them automatically
 */

(function() {
    'use strict';

    const STORAGE_KEY = 'django_admin_theme';

    /**
     * Listen for storage events (theme changes in other tabs/windows)
     */
    window.addEventListener('storage', function(e) {
        if (e.key === STORAGE_KEY && e.newValue) {
            // Theme was changed in another tab (like admin portal)
            if (window.GlobalThemeLoader) {
                window.GlobalThemeLoader.applyTheme(e.newValue);
                console.log('Theme synced from another tab:', e.newValue);
            }
        }
    });

    // Also check periodically for theme changes (backup method)
    let lastTheme = localStorage.getItem(STORAGE_KEY);
    
    setInterval(function() {
        const currentTheme = localStorage.getItem(STORAGE_KEY);
        if (currentTheme && currentTheme !== lastTheme) {
            if (window.GlobalThemeLoader) {
                window.GlobalThemeLoader.applyTheme(currentTheme);
                console.log('Theme changed detected:', currentTheme);
            }
            lastTheme = currentTheme;
        }
    }, 1000); // Check every second
})();
