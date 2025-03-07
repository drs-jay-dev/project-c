/**
 * DoctorsStudio CRM Custom Admin JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Dark mode functionality
    initDarkMode();
    
    // EST Clock functionality
    initESTClock();
    
    // Enhanced form interactions
    enhanceFormInteractions();
    
    // Initialize any custom widgets
    initCustomWidgets();
});

/**
 * Initialize dark mode toggle functionality
 */
function initDarkMode() {
    const darkModeToggle = document.getElementById('darkmode-toggle');
    if (!darkModeToggle) return;
    
    const darkModeIcon = document.getElementById('dark-mode-icon');
    const lightModeIcon = document.getElementById('light-mode-icon');
    const htmlElement = document.documentElement;
    
    // Check for saved theme preference or use preferred color scheme
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        htmlElement.setAttribute('data-theme', savedTheme);
        updateIcons(savedTheme);
    } else {
        const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (prefersDarkMode) {
            htmlElement.setAttribute('data-theme', 'dark');
            updateIcons('dark');
        }
    }
    
    // Toggle dark/light mode
    darkModeToggle.addEventListener('click', function() {
        const currentTheme = htmlElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        htmlElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateIcons(newTheme);
    });
    
    function updateIcons(theme) {
        if (theme === 'dark') {
            darkModeIcon.style.display = 'none';
            lightModeIcon.style.display = 'block';
        } else {
            darkModeIcon.style.display = 'block';
            lightModeIcon.style.display = 'none';
        }
    }
}

/**
 * Initialize EST clock functionality
 */
function initESTClock() {
    const clockElement = document.getElementById('est-clock');
    if (!clockElement) return;
    
    function updateClock() {
        const now = new Date();
        // Convert to EST (UTC-5)
        const estOptions = { 
            timeZone: 'America/New_York',
            hour12: true,
            weekday: 'short',
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        };
        
        const estTimeString = now.toLocaleString('en-US', estOptions);
        clockElement.textContent = estTimeString;
    }
    
    // Update clock immediately and then every second
    updateClock();
    setInterval(updateClock, 1000);
    
    // Also update login page clock if it exists
    const loginClockElement = document.getElementById('est-clock-login');
    if (loginClockElement) {
        function updateLoginClock() {
            const now = new Date();
            const estOptions = { 
                timeZone: 'America/New_York',
                hour12: true,
                weekday: 'short',
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            };
            
            const estTimeString = now.toLocaleString('en-US', estOptions);
            loginClockElement.textContent = estTimeString;
        }
        
        updateLoginClock();
        setInterval(updateLoginClock, 1000);
    }
}

/**
 * Enhance form interactions with modern behaviors
 */
function enhanceFormInteractions() {
    // Add focus and blur effects to form inputs
    const formInputs = document.querySelectorAll('input[type=text], input[type=password], input[type=email], input[type=url], input[type=number], textarea, select, .vTextField');
    
    formInputs.forEach(input => {
        // Add focused class on focus
        input.addEventListener('focus', function() {
            this.parentNode.classList.add('focused');
        });
        
        // Remove focused class on blur
        input.addEventListener('blur', function() {
            this.parentNode.classList.remove('focused');
        });
        
        // Add has-content class if input has value
        if (input.value) {
            input.parentNode.classList.add('has-content');
        }
        
        // Update has-content class on input
        input.addEventListener('input', function() {
            if (this.value) {
                this.parentNode.classList.add('has-content');
            } else {
                this.parentNode.classList.remove('has-content');
            }
        });
    });
    
    // Enhance select dropdowns
    const selectElements = document.querySelectorAll('select');
    selectElements.forEach(select => {
        select.addEventListener('change', function() {
            if (this.value) {
                this.classList.add('selected');
            } else {
                this.classList.remove('selected');
            }
        });
        
        // Set initial state
        if (select.value) {
            select.classList.add('selected');
        }
    });
}

/**
 * Initialize custom widgets and components
 */
function initCustomWidgets() {
    // Initialize any tooltips
    initTooltips();
    
    // Initialize collapsible sections
    initCollapsibleSections();
    
    // Initialize any custom tabs
    initTabs();
}

/**
 * Initialize tooltip functionality
 */
function initTooltips() {
    const tooltipElements = document.querySelectorAll('[data-tooltip]');
    
    tooltipElements.forEach(element => {
        const tooltipText = element.getAttribute('data-tooltip');
        
        // Create tooltip element
        const tooltip = document.createElement('div');
        tooltip.className = 'tooltip';
        tooltip.textContent = tooltipText;
        
        // Add tooltip behavior
        element.addEventListener('mouseenter', function() {
            document.body.appendChild(tooltip);
            const rect = element.getBoundingClientRect();
            
            tooltip.style.top = `${rect.bottom + window.scrollY + 5}px`;
            tooltip.style.left = `${rect.left + window.scrollX + (rect.width / 2) - (tooltip.offsetWidth / 2)}px`;
            tooltip.style.opacity = '1';
        });
        
        element.addEventListener('mouseleave', function() {
            if (tooltip.parentNode) {
                document.body.removeChild(tooltip);
            }
        });
    });
}

/**
 * Initialize collapsible sections
 */
function initCollapsibleSections() {
    const collapsibleHeaders = document.querySelectorAll('.collapsible-header');
    
    collapsibleHeaders.forEach(header => {
        header.addEventListener('click', function() {
            const content = this.nextElementSibling;
            
            // Toggle the active class
            this.classList.toggle('active');
            
            // Toggle visibility of content
            if (content.style.maxHeight) {
                content.style.maxHeight = null;
            } else {
                content.style.maxHeight = content.scrollHeight + 'px';
            }
        });
    });
}

/**
 * Initialize tabs functionality
 */
function initTabs() {
    const tabGroups = document.querySelectorAll('.tab-group');
    
    tabGroups.forEach(group => {
        const tabs = group.querySelectorAll('.tab');
        const tabContents = group.querySelectorAll('.tab-content');
        
        tabs.forEach((tab, index) => {
            tab.addEventListener('click', function() {
                // Remove active class from all tabs and contents
                tabs.forEach(t => t.classList.remove('active'));
                tabContents.forEach(c => c.classList.remove('active'));
                
                // Add active class to clicked tab and corresponding content
                this.classList.add('active');
                tabContents[index].classList.add('active');
            });
        });
        
        // Activate first tab by default
        if (tabs.length > 0) {
            tabs[0].click();
        }
    });
}
