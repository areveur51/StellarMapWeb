/**
 * Django Admin Theme Switcher
 * Allows switching between Cyberpunk, Borg Green, and Predator Red themes
 */

(function() {
    'use strict';

    const THEMES = {
        cyberpunk: {
            name: 'Cyberpunk',
            cssFile: '/static/webApp/css/admin_cyberpunk.css',
            description: 'Purple and cyan cyberpunk theme with glowing effects'
        },
        borg: {
            name: 'Borg Green',
            cssFile: '/static/webApp/css/admin_borg_theme.css',
            description: 'Star Trek Borg matrix green with assimilation vibes'
        },
        predator: {
            name: 'Predator Red',
            cssFile: '/static/webApp/css/admin_predator_theme.css',
            description: 'Predator thermal HUD red with hunting mode effects'
        }
    };

    const STORAGE_KEY = 'django_admin_theme';
    const DEFAULT_THEME = 'cyberpunk';

    /**
     * Get current theme from localStorage or default
     */
    function getCurrentTheme() {
        return localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME;
    }

    /**
     * Save theme preference to localStorage
     */
    function saveTheme(themeId) {
        localStorage.setItem(STORAGE_KEY, themeId);
    }

    /**
     * Remove all theme stylesheets
     */
    function removeThemeStylesheets() {
        const themeLinks = document.querySelectorAll('link[data-theme-stylesheet]');
        themeLinks.forEach(link => link.remove());
    }

    /**
     * Apply a theme by adding its CSS file
     */
    function applyTheme(themeId) {
        if (!THEMES[themeId]) {
            console.error(`Theme "${themeId}" not found. Using default.`);
            themeId = DEFAULT_THEME;
        }

        // Remove existing theme stylesheets
        removeThemeStylesheets();

        // Create and append new theme stylesheet
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.type = 'text/css';
        link.href = THEMES[themeId].cssFile;
        link.setAttribute('data-theme-stylesheet', themeId);
        document.head.appendChild(link);

        // Save preference
        saveTheme(themeId);

        // Update selector if it exists
        updateThemeSelector(themeId);

        // Add visual feedback
        showThemeChangeNotification(THEMES[themeId].name);
    }

    /**
     * Update theme selector dropdown to reflect current theme
     */
    function updateThemeSelector(themeId) {
        const selector = document.getElementById('admin-theme-selector');
        if (selector) {
            selector.value = themeId;
        }
    }

    /**
     * Show a brief notification when theme changes
     */
    function showThemeChangeNotification(themeName) {
        // Guard: Don't show notification if body doesn't exist yet (during init)
        if (!document.body) {
            return;
        }

        // Remove existing notification
        const existing = document.getElementById('theme-change-notification');
        if (existing) {
            existing.remove();
        }

        // Create notification
        const notification = document.createElement('div');
        notification.id = 'theme-change-notification';
        notification.textContent = `Theme: ${themeName}`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            background: rgba(0, 0, 0, 0.9);
            border: 1px solid currentColor;
            border-radius: 6px;
            color: inherit;
            font-size: 14px;
            z-index: 10000;
            opacity: 0;
            transition: opacity 0.3s ease;
            pointer-events: none;
        `;
        document.body.appendChild(notification);

        // Fade in
        setTimeout(() => {
            notification.style.opacity = '1';
        }, 10);

        // Fade out and remove
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 2000);
    }

    /**
     * Create theme selector dropdown
     */
    function createThemeSelector() {
        const container = document.createElement('div');
        container.id = 'admin-theme-selector-container';
        container.style.cssText = `
            display: inline-block;
            margin-left: 20px;
        `;

        const label = document.createElement('label');
        label.htmlFor = 'admin-theme-selector';
        label.textContent = 'Theme: ';
        label.style.cssText = `
            color: inherit;
            margin-right: 8px;
            font-size: 13px;
        `;

        const selector = document.createElement('select');
        selector.id = 'admin-theme-selector';
        selector.style.cssText = `
            background: rgba(0, 0, 0, 0.3);
            color: inherit;
            border: 1px solid currentColor;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 13px;
            cursor: pointer;
            outline: none;
            transition: all 0.3s ease;
        `;

        // Add options
        Object.entries(THEMES).forEach(([id, theme]) => {
            const option = document.createElement('option');
            option.value = id;
            option.textContent = theme.name;
            option.title = theme.description;
            selector.appendChild(option);
        });

        // Set current theme
        selector.value = getCurrentTheme();

        // Handle theme change
        selector.addEventListener('change', (e) => {
            applyTheme(e.target.value);
        });

        // Hover effect
        selector.addEventListener('mouseenter', () => {
            selector.style.borderColor = 'inherit';
            selector.style.boxShadow = '0 0 10px currentColor';
        });

        selector.addEventListener('mouseleave', () => {
            selector.style.boxShadow = 'none';
        });

        container.appendChild(label);
        container.appendChild(selector);

        return container;
    }

    /**
     * Initialize theme system
     */
    function init() {
        // Apply saved theme or default
        const currentTheme = getCurrentTheme();
        applyTheme(currentTheme);

        // Add theme selector to header when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', addThemeSelectorToHeader);
        } else {
            addThemeSelectorToHeader();
        }
    }

    /**
     * Add theme selector to the admin header
     */
    function addThemeSelectorToHeader() {
        // Try to find user tools section in header
        const userTools = document.getElementById('user-tools');
        if (userTools) {
            const selector = createThemeSelector();
            userTools.insertBefore(selector, userTools.firstChild);
            return;
        }
        
        // Try header element
        const header = document.getElementById('header');
        if (header) {
            const selector = createThemeSelector();
            selector.style.cssText = `
                position: relative;
                float: right;
                margin: 10px 20px;
                display: inline-block;
            `;
            // Insert at the end of header
            header.appendChild(selector);
            return;
        }
        
        // Fallback to body with fixed positioning
        const selector = createThemeSelector();
        selector.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            background: rgba(0, 0, 0, 0.8);
            padding: 10px;
            border-radius: 6px;
            border: 1px solid currentColor;
        `;
        document.body.appendChild(selector);
    }

    // Initialize when script loads
    init();

    // Expose API for manual theme switching
    window.AdminThemeSwitcher = {
        applyTheme: applyTheme,
        getCurrentTheme: getCurrentTheme,
        getAvailableThemes: () => Object.keys(THEMES),
        getThemeInfo: (themeId) => THEMES[themeId]
    };

})();
