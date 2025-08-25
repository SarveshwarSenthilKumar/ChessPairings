// Function to get CSRF token from meta tag
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

// Set up AJAX to include CSRF token in all requests
$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", getCSRFToken());
        }
    }
});

// Function to add CSRF token to all forms
function addCSRFTokenToForms() {
    const forms = document.querySelectorAll('form');
    const csrfToken = getCSRFToken();
    
    forms.forEach(form => {
        // Check if form already has a CSRF token
        if (!form.querySelector('input[name="csrf_token"]')) {
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrf_token';
            csrfInput.value = csrfToken;
            form.prepend(csrfInput);
        }
    });
}

// Run when document is ready
document.addEventListener('DOMContentLoaded', function() {
    addCSRFTokenToForms();
    
    // Also add CSRF token to dynamically loaded forms
    const observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes.length) {
                addCSRFTokenToForms();
            }
        });
    });
    
    // Start observing the document with the configured parameters
    observer.observe(document.body, { childList: true, subtree: true });
});
