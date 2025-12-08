/**
 * Tour Configurations using Driver.js
 * All platform tours are defined here
 */

/**
 * Dashboard Tour
 * Introduction to the investment pipeline and key features
 */
function startDashboardTour() {
    // Driver.js is exposed as window.driver.js.driver
    if (!window.driver || !window.driver.js || !window.driver.js.driver) {
        console.error('Driver.js not properly loaded!');
        alert('Tour system not loaded. Please refresh the page.');
        return;
    }

    const dashboardDriver = window.driver.js.driver({
        showProgress: true,
        showButtons: ['next', 'previous', 'close'],
        allowClose: true,
        steps: [
            {
                element: '.discipline-compact-header',
                popover: {
                    title: 'Welcome to Your Investment Platform',
                    description: 'This platform helps you build systematic investing discipline. Let\'s take a quick tour!',
                    side: "bottom",
                    align: 'start'
                }
            },
            {
                element: '.discipline-compact-stat',
                popover: {
                    title: 'Filter Rate - Your Discipline Metric',
                    description: 'Most successful investors say "no" to 90%+ of ideas. This shows how selective you are. Being picky is good!',
                    side: "left",
                    align: 'start'
                }
            },
            {
                element: '.pipeline-flow-main',
                popover: {
                    title: 'Investment Pipeline',
                    description: 'This is your systematic process: Ideas → Screen → Research → Portfolio. Every company flows through this pipeline.',
                    side: "top",
                    align: 'start'
                }
            },
            {
                element: '.too-hard-basket',
                popover: {
                    title: 'Too Hard Basket - Your Discipline Bucket',
                    description: 'Companies you reject go here. This isn\'t failure - it\'s discipline. You\'re avoiding bad investments.',
                    side: "top",
                    align: 'start'
                }
            },
            {
                element: '.dashboard-header-actions',
                popover: {
                    title: 'Quick Actions',
                    description: 'Use Quick Add to add investment ideas, journal entries, or log mistakes. Start here when you have a new idea!',
                    side: "left",
                    align: 'start'
                }
            },
            {
                element: '.priorities-section-sidebar',
                popover: {
                    title: 'Today\'s Priorities',
                    description: 'Focus on a few companies deeply rather than many superficially. Your most important tasks appear here.',
                    side: "top",
                    align: 'start'
                }
            },
            {
                popover: {
                    title: 'Ready to Start!',
                    description: 'You understand the basics! Real investing requires time and discipline. Click "Quick Add" to add your first investment idea, or explore other features at your own pace.',
                }
            }
        ],
        onDestroyed: () => {
            // Mark tour as completed when user finishes or closes
            markTourCompleted('dashboard');
        }
    });

    dashboardDriver.drive();
}

/**
 * Mark a tour as completed for the current user
 * @param {string} tourName - Name of the tour (e.g., 'dashboard', 'inbox')
 */
function markTourCompleted(tourName) {
    fetch('/api/mark-tour-completed', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ tour_name: tourName })
    })
    .then(response => response.json())
    .then(data => {
        console.log(`Tour "${tourName}" marked as completed`);
    })
    .catch(error => {
        console.error('Error marking tour as completed:', error);
    });
}

/**
 * Check if user should see a tour
 * @param {string} tourName - Name of the tour
 * @returns {Promise<boolean>} - Whether to show the tour
 */
async function shouldShowTour(tourName) {
    try {
        const response = await fetch(`/api/should-show-tour?tour_name=${tourName}`);
        const data = await response.json();
        return data.should_show;
    } catch (error) {
        console.error('Error checking tour status:', error);
        return false;
    }
}

// Debug: Check if Driver.js loaded correctly
console.log('Tours.js loaded. Driver.js available:', !!(window.driver && window.driver.js && window.driver.js.driver));
