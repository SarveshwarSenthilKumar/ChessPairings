// Handle hide tournament button clicks
document.addEventListener('DOMContentLoaded', function() {
    document.addEventListener('click', async function(e) {
        const hideBtn = e.target.closest('.hide-tournament');
        if (!hideBtn) return;
        
        e.preventDefault();
        const tournamentId = hideBtn.dataset.tournamentId;
        
        if (!tournamentId) {
            console.error('No tournament ID found on hide button');
            return;
        }
        
        // Get CSRF token
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            console.error('CSRF token not found');
            showErrorToast('Security error. Please refresh the page and try again.');
            return;
        }
        
        try {
            const response = await fetch(`/tournament/${tournamentId}/hide`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Remove the tournament card from the DOM
                const card = hideBtn.closest('.col-12.col-md-6.col-lg-4.mb-4');
                if (card) {
                    card.style.opacity = '0';
                    setTimeout(() => {
                        card.remove();
                        
                        // If no more tournaments, show empty state
                        const tournamentContainer = document.querySelector('.row');
                        const tournamentCards = tournamentContainer.querySelectorAll('.col-12.col-md-6.col-lg-4.mb-4');
                        
                        if (tournamentCards.length === 0) {
                            const emptyState = `
                                <div class="col-12">
                                    <div class="card text-center p-5">
                                        <i class="fas fa-inbox fa-4x text-muted mb-3"></i>
                                        <h3>No tournaments found</h3>
                                        <p class="text-muted">You don't have any tournaments to display.</p>
                                        <a href="{{ url_for('tournament.create') }}" class="btn btn-primary mt-3">
                                            <i class="fas fa-plus me-2"></i>Create Tournament
                                        </a>
                                    </div>
                                </div>`;
                            tournamentContainer.innerHTML = emptyState;
                        }
                    }, 300);
                }
            } else {
                showErrorToast(data.message || 'Failed to hide tournament');
            }
        } catch (error) {
            console.error('Error hiding tournament:', error);
            showErrorToast('An error occurred while hiding the tournament');
        }
    });
});

// Helper function to show error toasts
function showErrorToast(message) {
    // Check if toast container exists, if not create it
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastId = 'error-toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white bg-danger" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>`;
    
    // Add toast to container
    toastContainer.insertAdjacentHTML('beforeend', toastHtml);
    
    // Initialize and show toast
    const toastEl = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastEl, { autohide: true, delay: 5000 });
    toast.show();
    
    // Remove toast after it's hidden
    toastEl.addEventListener('hidden.bs.toast', function() {
        toastEl.remove();
    });
}
