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

if (typeof tailwind !== 'undefined') {
    tailwind.config = {
        darkMode: 'class',
        theme: {
            extend: {
                colors: window.slieTheme.colors,
                fontFamily: window.slieTheme.fonts,
                boxShadow: window.slieTheme.shadows,
                animation: {
                    'pulse-slow': 'pulse 6s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                    'fade-in': 'fadeIn 0.8s ease-out forwards',
                    'slide-up': 'slideUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards',
                    'float': 'float 4s ease-in-out infinite',
                },
                keyframes: {
                    fadeIn: {
                        '0%': { opacity: '0' },
                        '100%': { opacity: '1' },
                    },
                    slideUp: {
                        '0%': { transform: 'translateY(30px)', opacity: '0' },
                        '100%': { transform: 'translateY(0)', opacity: '1' },
                    },
                    float: {
                        '0%, 100%': { transform: 'translateY(0)' },
                        '50%': { transform: 'translateY(-10px)' },
                    }
                }
            }
        }
    };
}
