// Empty JavaScript file - placeholder for future custom scripts
console.log('my_script.js loaded');

/**
 * Quote Banner Dismissal
 * Handles dismissing the investor quote banner with animation
 */
document.addEventListener('DOMContentLoaded', function() {
    const dismissBtn = document.querySelector('[data-action="dismiss-quote-banner"]');

    if (dismissBtn) {
        dismissBtn.addEventListener('click', function() {
            const banner = document.getElementById('quote-banner');

            // Add dismissing animation
            banner.classList.add('dismissing');

            // Send AJAX request to save preference
            fetch('/api/dismiss-quote-banner', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Quote banner preference saved');
                }
            })
            .catch(error => {
                console.error('Error saving quote banner preference:', error);
            });

            // Remove banner from DOM after animation completes
            setTimeout(() => {
                banner.remove();
            }, 300);
        });
    }
});