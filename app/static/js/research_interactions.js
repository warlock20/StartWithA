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
    if (!form) {
        console.error('AI Analysis Form not found');
        return; 
    }

    var resultDiv = document.getElementById('aiAnalysisResult');
    if (!resultDiv) {
        console.error('AI Analysis Result div not found');
        return;
    }

    // 1. Clear previous results and show the CORRECT loading indicator WITH the spinner
    resultDiv.innerHTML = '<div class="loader"></div><p><em>AI is analyzing, please wait...</em></p>';

    var selectedDocCheckboxes = form.querySelectorAll('input[name="selected_document_ids"]:checked');
    var selectedDocumentIds = [];
    selectedDocCheckboxes.forEach(function(checkbox) {
        selectedDocumentIds.push(checkbox.value);
    });

    var llmPromptInput = form.querySelector('input[name="llm_actual_prompt"]');
    var llmPrompt = llmPromptInput ? llmPromptInput.value : '';

    const analysisUrl = form.dataset.analysisUrl;
    if (!analysisUrl) {
        resultDiv.innerHTML = '<p style="color:red;"><em>Error: Analysis URL not configured. Cannot submit.</em></p>';
        console.error('Error: Analysis URL not found on form data attribute.');
        return;
    }
    
    const selectedModelInput = form.querySelector('input[name="selected_ai_model"]:checked');
    const selectedModel = selectedModelInput ? selectedModelInput.value : 'local'; // Default to 'local' if none selected


    try {
        const response = await fetch(analysisUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // Add CSRF token here if/when implemented
            },
            body: JSON.stringify({
                llm_actual_prompt: llmPrompt,
                selected_document_ids: selectedDocumentIds,
                selected_model: selectedModel 
            })
        });
        resultDiv.innerHTML = ''; // Clear loader
        // At this point, the fetch is complete. We will replace the loader with the result or an error.
        // No need to set resultDiv.innerHTML to the loader again here.
        // The following lines will overwrite the loader.

        if (!response.ok) {
            let errorData;
            try { errorData = await response.json(); } catch (e) { errorData = { message: response.statusText || `HTTP error! Status: ${response.status}` }; }
            throw new Error(errorData.message || `HTTP error! Status: ${response.status}`);
        }

        const data = await response.json(); 
        
        let statusClass = '';
        if (data.status && data.status.startsWith('error_')) {
            statusClass = 'ai-error';
        } else if (data.status && data.status.startsWith('warning_')) {
            statusClass = 'ai-warning';
        } else if (data.status && data.status.startsWith('success_')) {
            statusClass = 'ai-success';
        }

        let prettyResponse = `<div class="${statusClass}"><h4>AI Analysis Result:</h4>`;
        prettyResponse += `<p><strong>Status:</strong> ${escapeHtml(data.status)}</p>`;
        prettyResponse += `<p><strong>Message:</strong> ${escapeHtml(data.message)}</p></div>`;
        
        if (data.received_prompt) {
            prettyResponse += '<p><strong>Original Prompt:</strong> ' + escapeHtml(data.received_prompt) + '</p>';
        }

        if (data.selected_documents_info && data.selected_documents_info.length > 0) {
            prettyResponse += '<p><strong>Processed Documents:</strong></p><ul>';
            data.selected_documents_info.forEach(function(doc) {
                prettyResponse += '<li>' + escapeHtml(doc.title || doc.filename) + ' (ID: ' + escapeHtml(doc.id) + ')</li>';
            });
            prettyResponse += '</ul>';
        } else if (!data.selected_documents_info && selectedDocumentIds.length > 0 && !data.status.includes("_no_documents_selected")) {
             prettyResponse += '<p>Documents were selected, but no detailed info returned from server (check server logs for validation issues).</p>';
        } else if (!data.status.includes("_no_documents_selected")){ // Avoid double message if status already says no docs
            prettyResponse += '<p>No documents were specified or processed for context.</p>';
        }


        if (data.extracted_text_sample && data.extracted_text_sample.trim() !== '' && !data.extracted_text_sample.startsWith("---")) { // Only show if meaningful
            prettyResponse += '<p><strong>Sample of Text Provided to AI:</strong></p>';
            prettyResponse += '<pre style="white-space: pre-wrap; border: 1px solid #ccc; padding: 5px; max-height: 100px; overflow-y: auto; background-color: #f9f9f9;">' + escapeHtml(data.extracted_text_sample) + '</pre>';
        }

        // Display AI suggestion only if the status indicates success or a warning where a suggestion might still be present
        if (data.ai_suggestion && (data.status.includes('success_') || data.status.includes('warning_'))) {
            // Avoid showing the default "AI model unavailable" or error messages as a "suggestion" if status is error
            if (!data.status.startsWith('error_')) {
                 prettyResponse += '<p><strong>AI Suggestion:</strong></p>';
                 prettyResponse += '<div id="aiSuggestionText" style="background-color: #f0f0f0; border: 1px solid #ccc; padding: 10px; margin-top: 5px; white-space: pre-wrap;">' + escapeHtml(data.ai_suggestion) + '</div>';
                 prettyResponse += '<button type="button" onclick="useAISuggestion()" style="margin-top: 5px;">Use this Suggestion</button>';
            }
        }
        resultDiv.innerHTML = prettyResponse;

    } catch (error) {
        console.error('Error submitting for AI analysis:', error);
        resultDiv.innerHTML = '<div class="ai-error"><h4>AI Analysis Error:</h4><p><em>' + escapeHtml(error.message) + '</em></p></div>';
    }
}

// Make sure escapeHtml and useAISuggestion functions are also in this file
function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return String(unsafe) // Ensure it's a string before replacing
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

function useAISuggestion() {
    var suggestionTextDiv = document.getElementById('aiSuggestionText');
    var answerTextarea = document.getElementById('answer_text'); // ID of your main answer textarea
    
    if (suggestionTextDiv && answerTextarea) {
        answerTextarea.value = suggestionTextDiv.innerText || suggestionTextDiv.textContent; // Use innerText to get displayed text
    } else {
        if (!suggestionTextDiv) console.error("AI suggestion text container not found.");
        if (!answerTextarea) console.error("Main answer textarea not found.");
    }
}

// The DOMContentLoaded listener to attach event handlers should already be in this file.
// Ensure it's correctly attaching to 'submitAIAnalysisPlaceholderButton'.
document.addEventListener('DOMContentLoaded', function() {
    const analyzeButton = document.getElementById('analyzeWithAIButton');
    if (analyzeButton) {
        analyzeButton.addEventListener('click', toggleAIDocsSelection);
    }

    const submitAIButton = document.getElementById('submitAIAnalysisPlaceholderButton');
    if (submitAIButton) {
        // Ensure this button type is "button" not "submit" if it's inside the main form,
        // or that this function prevents default form submission if necessary.
        // Since it's calling fetch, it shouldn't submit the outer form.
        submitAIButton.addEventListener('click', submitForAIAnalysis);
    }
});