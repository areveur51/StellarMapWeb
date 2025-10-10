/*
 * global_theme_loader.js
 * Global theme loader for entire StellarMapWeb application
 * Shares theme preference with admin portal via localStorage
 * 
 * Features:
 * - Automatic theme application on page load
 * - Syncs with admin theme selector
 * - Uses same localStorage key for consistency
 * - Dynamic CSS loading for main application pages
 */

(function() {
    'use strict';

    // Theme configuration matching admin themes
    const THEMES = {
        cyberpunk: {
            name: 'Cyberpunk',
            cssFile: '/static/webApp/css/cyberpunk_theme.css'
        },
        borg: {
            name: 'Borg Green',
            cssFile: '/static/webApp/css/borg_theme.css'
        },
        predator: {
            name: 'Predator Red',
            cssFile: '/static/webApp/css/predator_theme.css'
        }
    };

    // Same localStorage key as admin theme switcher
    const STORAGE_KEY = 'django_admin_theme';
    const DEFAULT_THEME = 'cyberpunk';

    /**
     * Get current theme from localStorage
     */
    function getCurrentTheme() {
        const savedTheme = localStorage.getItem(STORAGE_KEY);
        return (savedTheme && THEMES[savedTheme]) ? savedTheme : DEFAULT_THEME;
    }

    /**
     * Remove all theme CSS links from document
     */
    function removeAllThemeLinks() {
        Object.values(THEMES).forEach(theme => {
            const existingLink = document.querySelector(`link[href="${theme.cssFile}"]`);
            if (existingLink) {
                existingLink.remove();
            }
        });
    }

    /**
     * Load theme CSS file
     */
    function loadThemeCSS(themeId) {
        const theme = THEMES[themeId];
        if (!theme) return;

        // Remove all existing theme links
        removeAllThemeLinks();

        // Check if theme CSS is already loaded
        const existingLink = document.querySelector(`link[href="${theme.cssFile}"]`);
        if (existingLink) return;

        // Create and insert new theme link
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = theme.cssFile;
        link.id = `theme-${themeId}`;
        
        // Insert after frontend.css or at the end of head
        const frontendCSS = document.querySelector('link[href*="frontend.css"]');
        if (frontendCSS && frontendCSS.parentNode) {
            frontendCSS.parentNode.insertBefore(link, frontendCSS);
        } else {
            document.head.appendChild(link);
        }
    }

    /**
     * Apply theme on page load
     */
    function applyTheme() {
        const currentTheme = getCurrentTheme();
        loadThemeCSS(currentTheme);
    }

    /**
     * Initialize theme on DOM ready
     */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyTheme);
    } else {
        applyTheme();
    }

    // Expose API for manual theme changes (if needed)
    window.GlobalThemeLoader = {
        applyTheme: function(themeId) {
            if (THEMES[themeId]) {
                localStorage.setItem(STORAGE_KEY, themeId);
                loadThemeCSS(themeId);
            }
        },
        getCurrentTheme: getCurrentTheme
    };
})();
