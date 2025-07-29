// In app/static/js/financials_charts.js

// Helper function to format large numbers for tooltips and axes
function formatNumber(value) {
    if (Math.abs(value) >= 1e12) {
        return (value / 1e12).toFixed(2) + ' T';
    }
    if (Math.abs(value) >= 1e9) {
        return (value / 1e9).toFixed(2) + ' B';
    }
    if (Math.abs(value) >= 1e6) {
        return (value / 1e6).toFixed(2) + ' M';
    }
    return value.toLocaleString();
}

document.addEventListener('DOMContentLoaded', function() {
    // This script expects a 'pageChartData' object to be defined in the HTML
    if (typeof pageChartData === 'undefined') {
        console.error('Chart data not found!');
        return;
    }

    // --- Render Revenue Chart ---
    const revenueCtx = document.getElementById('revenueChart');
    if (revenueCtx && pageChartData.revenue && pageChartData.revenue.values.length > 0) {
        new Chart(revenueCtx, {
            type: 'bar',
            data: {
                labels: pageChartData.revenue.labels,
                datasets: [{
                    label: 'Total Revenue',
                    data: pageChartData.revenue.values,
                    backgroundColor: 'rgba(54, 162, 235, 0.8)',
                }]
            },
            options: {
                responsive: true,
                plugins: { tooltip: { callbacks: { label: (ctx) => ' ' + formatNumber(ctx.raw) } } },
                scales: { y: { ticks: { callback: (val) => formatNumber(val) } } }
            }
        });
    }

    // --- Render Net Income Chart ---
    const netIncomeCtx = document.getElementById('netIncomeChart');
    if (netIncomeCtx && pageChartData.net_income && pageChartData.net_income.values.length > 0) {
        new Chart(netIncomeCtx, {
            type: 'line',
            data: {
                labels: pageChartData.net_income.labels,
                datasets: [{
                    label: 'Net Income',
                    data: pageChartData.net_income.values,
                    borderColor: 'rgba(75, 192, 192, 1)',
                    backgroundColor: 'rgba(75, 192, 192, 0.5)',
                    fill: true,
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                plugins: { tooltip: { callbacks: { label: (ctx) => ' ' + formatNumber(ctx.raw) } } },
                scales: { y: { ticks: { callback: (val) => formatNumber(val) } } }
            }
        });
    }
});