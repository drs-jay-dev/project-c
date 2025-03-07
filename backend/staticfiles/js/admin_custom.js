// DoctorsStudio CRM Admin Customizations

document.addEventListener('DOMContentLoaded', function() {
    // Ensure sidebar is always visible
    function ensureSidebarVisible() {
        const sidebar = document.getElementById('nav-sidebar');
        if (sidebar) {
            sidebar.style.display = 'block';
            
            // Make sure the toggle button is in the correct state
            const toggleButton = document.getElementById('toggle-nav-sidebar');
            if (toggleButton) {
                toggleButton.setAttribute('aria-expanded', 'true');
            }
            
            // Add a class to the body to indicate sidebar is open
            document.body.classList.add('nav-sidebar-expanded');
        }
    }
    
    // Call immediately and also set up a mutation observer to handle dynamic changes
    ensureSidebarVisible();
    
    // Set up an observer to watch for changes to the DOM
    const observer = new MutationObserver(function(mutations) {
        ensureSidebarVisible();
    });
    
    // Start observing the document body for changes
    observer.observe(document.body, { 
        childList: true,
        subtree: true
    });
    
    // Also run on window resize
    window.addEventListener('resize', ensureSidebarVisible);
    
    // And run periodically just to be sure
    setInterval(ensureSidebarVisible, 1000);
});
