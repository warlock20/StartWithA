/**
 * Sector Research Sources - Data Table
 * Initializes Tabulator table for research sources with sorting, filtering, and export
 */

document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the sector analysis page and sources tab exists
    const sourcesTable = document.getElementById('sources-table');

    if (!sourcesTable) {
        return; // Not on sources page
    }

    if (typeof window.sourcesData === 'undefined') {
        console.error('Sources data not available');
        return;
    }

    // Initialize the sources table
    initializeSourcesTable();
});

/**
 * Initialize the sources data table
 */
function initializeSourcesTable() {
    const table = createDataTable('#sources-table', {
        data: window.sourcesData,
        columns: [
            {
                title: "Type",
                field: "source_type",
                width: 120,
                sorter: "string",
                headerFilter: "list",
                headerFilterParams: {
                    values: {
                        "": "All Types",
                        "article": "Article",
                        "report": "Report",
                        "video": "Video",
                        "podcast": "Podcast",
                        "gemini": "AI Generated",
                        "other": "Other"
                    },
                    clearable: true
                },
                formatter: function(cell) {
                    const type = cell.getValue();
                    const iconMap = {
                        'article': '<i class="bi bi-newspaper"></i>',
                        'report': '<i class="bi bi-file-earmark-text"></i>',
                        'video': '<i class="bi bi-play-circle"></i>',
                        'podcast': '<i class="bi bi-mic"></i>',
                        'gemini': '<i class="bi bi-stars"></i>',
                        'other': '<i class="bi bi-bookmark"></i>'
                    };
                    const colorMap = {
                        'article': 'bg-primary',
                        'report': 'bg-info',
                        'video': 'bg-danger',
                        'podcast': 'bg-warning',
                        'gemini': 'bg-success',
                        'other': 'bg-secondary'
                    };
                    const icon = iconMap[type] || iconMap['other'];
                    const color = colorMap[type] || colorMap['other'];
                    const label = type.charAt(0).toUpperCase() + type.slice(1);
                    return `<span class="badge ${color}">${icon} ${label}</span>`;
                }
            },
            {
                title: "Title",
                field: "title",
                sorter: "string",
                headerFilter: "input",
                headerFilterPlaceholder: "Search titles...",
                minWidth: 200,
                widthGrow: 2,
                formatter: function(cell) {
                    const value = cell.getValue();
                    return `<strong>${value}</strong>`;
                }
            },
            {
                title: "URL",
                field: "url",
                sorter: "string",
                widthGrow: 2,
                formatter: function(cell) {
                    const url = cell.getValue();
                    const row = cell.getRow().getData();

                    if (!url) {
                        return '<span class="text-muted">--</span>';
                    }

                    // Truncate URL for display
                    let displayUrl = url;
                    if (url.length > 50) {
                        displayUrl = url.substring(0, 47) + '...';
                    }

                    return `<a href="${url}"
                               target="_blank"
                               class="text-primary text-decoration-none"
                               onclick="markSourceAccessed(${row.id}); event.stopPropagation();"
                               title="${url}">
                        <i class="bi bi-box-arrow-up-right"></i> ${displayUrl}
                    </a>`;
                }
            },
            {
                title: "Description",
                field: "description",
                sorter: "string",
                widthGrow: 3,
                formatter: function(cell) {
                    const value = cell.getValue();
                    if (!value) {
                        return '<span class="text-muted">--</span>';
                    }
                    // Truncate long descriptions
                    if (value.length > 100) {
                        return `<span class="text-muted" title="${value}">${value.substring(0, 97)}...</span>`;
                    }
                    return `<span class="text-muted">${value}</span>`;
                }
            },
            {
                title: "Added",
                field: "created_at",
                width: 110,
                sorter: "datetime",
                sorterParams: {
                    format: "iso"
                },
                formatter: function(cell) {
                    const value = cell.getValue();
                    if (!value) return '<span class="text-muted">--</span>';

                    const date = new Date(value);
                    return date.toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                    });
                }
            },
            {
                title: "Last Accessed",
                field: "accessed_at",
                width: 130,
                sorter: "datetime",
                sorterParams: {
                    format: "iso"
                },
                formatter: function(cell) {
                    const value = cell.getValue();
                    if (!value) return '<span class="text-muted">Never</span>';

                    const date = new Date(value);
                    return `<span class="text-muted">${date.toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric'
                    })}</span>`;
                }
            },
            {
                title: "Actions",
                field: "id",
                width: 80,
                hozAlign: "center",
                headerSort: false,
                formatter: function(cell) {
                    const sourceId = cell.getValue();

                    return `<button class="btn btn-sm btn-outline-danger"
                                    onclick="deleteSource(event, ${sourceId})"
                                    title="Delete source">
                        <i class="bi bi-trash"></i>
                    </button>`;
                }
            }
        ],
        exportButtons: true,
        exportConfig: {
            filename: 'sector-research-sources',
            csv: true,
            xlsx: false,
            json: false
        },
        customConfig: {
            initialSort: [
                { column: "created_at", dir: "desc" }
            ],
            layout: "fitDataStretch", // Stretch to fill container
            responsiveLayout: "collapse",
            pagination: true,
            paginationSize: 25,
            paginationSizeSelector: [10, 25, 50, 100]
        }
    });

    // Store table globally for potential updates
    window.sourcesTableInstance = table;
}

/**
 * Mark a source as accessed (track last accessed time)
 */
function markSourceAccessed(sourceId) {
    // Send AJAX request to update accessed_at timestamp
    fetch(`/sectors/source/${sourceId}/mark_accessed`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    }).catch(err => {
        console.error('Error marking source as accessed:', err);
    });
}

/**
 * Delete a source with confirmation
 */
function deleteSource(event, sourceId) {
    event.stopPropagation(); // Prevent row click

    if (!confirm('Are you sure you want to delete this source? This action cannot be undone.')) {
        return;
    }

    // Create and submit form
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = `/sectors/source/${sourceId}/delete`;
    form.style.display = 'none';
    document.body.appendChild(form);
    form.submit();
}

// Make functions globally accessible
window.markSourceAccessed = markSourceAccessed;
window.deleteSource = deleteSource;
