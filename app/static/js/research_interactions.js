function toggleAIDocsSelection() {
    var section = document.getElementById('aiDocumentSelection');
    if (section) { // Check if element exists
        if (section.style.display === 'none' || section.style.display === '') {
            section.style.display = 'block';
        } else {
            section.style.display = 'none';
        }
    }
}

async function submitForAIAnalysis() {
    var form = document.getElementById('aiAnalysisForm');
    var selectedDocCheckboxes = form.querySelectorAll('input[name="selected_document_ids"]:checked');
    var selectedDocumentIds = [];
    selectedDocCheckboxes.forEach(function (checkbox) {
        selectedDocumentIds.push(checkbox.value);
    });

    var llmPromptInput = form.querySelector('input[name="llm_actual_prompt"]');
    var llmPrompt = llmPromptInput ? llmPromptInput.value : ''; // Handle if input not found

    var resultDiv = document.getElementById('aiAnalysisResult');
    if (!resultDiv) return; // Guard clause

    resultDiv.innerHTML = '<em>Processing request with prompt: "' + llmPrompt + '" and ' + selectedDocumentIds.length + ' document(s)...</em>';

    const analysisUrl = form.dataset.analysisUrl; // Get URL from data attribute
    if (!analysisUrl) {
        resultDiv.innerHTML = '<em style="color:red;">Error: Analysis URL not configured.</em>';
        console.error('Error: Analysis URL not found on form data attribute.');
        return;
    }

    try {
        const response = await fetch(analysisUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // Add CSRF token here if/when implemented
            },
            body: JSON.stringify({
                llm_actual_prompt: llmPrompt,
                selected_document_ids: selectedDocumentIds
            })
        });

        if (!response.ok) {
            // Try to get error message from JSON response if backend sends one
            let errorData;
            try {
                errorData = await response.json();
            } catch (e) {
                errorData = { message: `HTTP error! status: ${response.status}` };
            }
            throw new Error(errorData.message || `HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        let prettyResponse = '<strong>AI Analysis Request Processed (Placeholder):</strong><br>';
        prettyResponse += 'Status: ' + data.status + '<br>';
        prettyResponse += 'Message: ' + data.message + '<br>';
        prettyResponse += 'Received Prompt: ' + data.received_prompt + '<br>';
        if (data.selected_documents_info && data.selected_documents_info.length > 0) {
            prettyResponse += 'Validated Documents Selected:<br><ul>';
            data.selected_documents_info.forEach(function (doc) {
                prettyResponse += '<li>' + (doc.title || doc.filename) + ' (ID: ' + doc.id + ')</li>';
            });
            prettyResponse += '</ul>';
        } else if (data.received_doc_ids && data.received_doc_ids.length > 0) {
            prettyResponse += 'Received Document IDs: ' + data.received_doc_ids.join(', ') + '<br>';
        } else {
            prettyResponse += 'No documents were selected or processed.<br>';
        }
        resultDiv.innerHTML = prettyResponse;

    } catch (error) {
        console.error('Error submitting for AI analysis:', error);
        resultDiv.innerHTML = '<em style="color:red;">Error: ' + error.message + '</em>';
    }
}

// Attach event listeners after the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    const analyzeButton = document.getElementById('analyzeWithAIButton'); // Give your "Analyze with AI..." button this ID
    if (analyzeButton) {
        analyzeButton.addEventListener('click', toggleAIDocsSelection);
    }

    const submitAIButton = document.getElementById('submitAIAnalysisPlaceholderButton'); // Give your "Submit for AI Analysis..." button this ID
    if (submitAIButton) {
        submitAIButton.addEventListener('click', submitForAIAnalysis);
    }
});