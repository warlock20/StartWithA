// In app/static/js/dashboard_charts.js

document.addEventListener('DOMContentLoaded', function () {
    // This script will look for a 'chartData' object provided by the HTML template
    if (typeof chartData === 'undefined') {
        console.error('Chart data not found!');
        return;
    }

    // --- 1. Sector Pie Chart ---
    const sectorCtx = document.getElementById('sectorPieChart');
    if (sectorCtx && chartData.sectorValues && chartData.sectorValues.length > 0) {
        new Chart(sectorCtx, {
            type: 'pie',
            data: {
                labels: chartData.sectorLabels,
                datasets: [{
                    label: '# of Companies',
                    data: chartData.sectorValues,
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.8)', 'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 206, 86, 0.8)', 'rgba(75, 192, 192, 0.8)',
                        'rgba(153, 102, 255, 0.8)', 'rgba(255, 159, 64, 0.8)'
                    ],
                    borderColor: ['rgba(255, 255, 255, 1)'],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'top' },
                    title: { display: false }
                }
            }
        });
    }

    // --- 2. Margin of Safety Bar Chart ---
    const mosCtx = document.getElementById('mosBarChart');
    if (mosCtx && chartData.mosValues && chartData.mosValues.length > 0) {
        const backgroundColors = chartData.mosValues.map(value => value <= 0 ? 'rgba(75, 192, 192, 0.8)' : 'rgba(255, 99, 132, 0.8)');

        new Chart(mosCtx, {
            type: 'bar',
            data: {
                labels: chartData.mosLabels,
                datasets: [{
                    label: 'Margin of Safety (%)',
                    data: chartData.mosValues,
                    backgroundColor: backgroundColors
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    title: { display: true, text: 'Positive = Overvalued, Negative = Undervalued' },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return ' MoS: ' + context.raw + '%';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        });
    }
});