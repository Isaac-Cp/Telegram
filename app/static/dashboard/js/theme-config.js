/**
 * SLIE Premium Intelligence - Centralized Theme Configuration
 * This file defines the core design tokens and tailwind configuration
 * used across the entire application to ensure visual consistency.
 */

window.slieTheme = {
    colors: {
        obsidian: '#01040d',
        'deep-blue': '#0a192f',
        glass: 'rgba(10, 25, 47, 0.7)',
        'glass-edge': 'rgba(100, 149, 237, 0.15)',
        accent: '#64ffda',
        highlight: '#3b82f6',
        clay: {
            base: '#112240',
            shadow: 'rgba(0, 0, 0, 0.4)',
            light: 'rgba(255, 255, 255, 0.05)'
        }
    },
    fonts: {
        sans: ['Plus Jakarta Sans', 'Inter', 'sans-serif'],
        serif: ['Lora', 'serif'],
    },
    shadows: {
        'glass': '0 8px 32px 0 rgba(0, 0, 0, 0.5)',
        'clay-card': '8px 8px 16px 0 rgba(0, 0, 0, 0.4), -4px -4px 12px 0 rgba(255, 255, 255, 0.03)',
        'clay-inset': 'inset 4px 4px 8px 0 rgba(0, 0, 0, 0.4), inset -4px -4px 8px 0 rgba(255, 255, 255, 0.03)',
        'clay-button': '6px 6px 12px 0 rgba(0, 0, 0, 0.4), -2px -2px 8px 0 rgba(255, 255, 255, 0.03), inset 2px 2px 4px 0 rgba(255, 255, 255, 0.05)',
        'clay-button-active': 'inset 4px 4px 8px 0 rgba(0, 0, 0, 0.5), inset -2px -2px 6px 0 rgba(255, 255, 255, 0.02)',
    }
};

function toggleMobileMenu() {
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
        sidebar.classList.toggle('active');
    }
}

// Smooth scrolling for all links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        document.querySelector(this.getAttribute('href')).scrollIntoView({
            behavior: 'smooth'
        });
    });
});
