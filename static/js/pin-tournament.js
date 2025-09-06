/**
 * Handles pin/unpin functionality for tournaments
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips for pin buttons
    const pinButtons = document.querySelectorAll('.pin-tournament');
    pinButtons.forEach(button => {
        // Initialize tooltip
        new bootstrap.Tooltip(button);
        
        // Set initial pinned state from session storage
        const tournamentId = button.dataset.tournamentId;
        const pinnedKey = `pinned_tournaments_${getUserId()}`;
        const pinnedTournaments = JSON.parse(sessionStorage.getItem(pinnedKey) || '[]');
        const isPinned = pinnedTournaments.includes(parseInt(tournamentId));
        
        updatePinButton(button, isPinned);
    });
    
    // Handle pin/unpin click
    document.addEventListener('click', function(e) {
        const pinButton = e.target.closest('.pin-tournament');
        if (!pinButton) return;
        
        e.preventDefault();
        const tournamentId = pinButton.dataset.tournamentId;
        const isPinned = pinButton.dataset.pinned === 'true';
        
        togglePinTournament(tournamentId, !isPinned, pinButton);
    });
    
    // Function to toggle pin status
    function togglePinTournament(tournamentId, pin, button) {
        const url = `/tournament/${tournamentId}/${pin ? 'pin' : 'unpin'}`;
        
        fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update UI
                updatePinButton(button, pin);
                
                // Show toast notification
                showToast(
                    pin ? 'Tournament Pinned' : 'Tournament Unpinned',
                    pin ? 'This tournament will now appear at the top of your list.' : 'This tournament has been unpinned.',
                    'success'
                );
                
                // Update session storage
                const pinnedKey = `pinned_tournaments_${getUserId()}`;
                let pinnedTournaments = JSON.parse(sessionStorage.getItem(pinnedKey) || '[]');
                
                if (pin) {
                    // Remove if exists to avoid duplicates and add to the beginning
                    pinnedTournaments = pinnedTournaments.filter(id => id !== parseInt(tournamentId));
                    pinnedTournaments.unshift(parseInt(tournamentId));
                } else {
                    pinnedTournaments = pinnedTournaments.filter(id => id !== parseInt(tournamentId));
                }
                
                sessionStorage.setItem(pinnedKey, JSON.stringify(pinnedTournaments));
                
                // Sort tournaments to ensure pinned ones are at the top
                sortTournaments();
            } else {
                showToast('Error', data.message || 'An error occurred', 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showToast('Error', 'An error occurred while updating the pin status', 'danger');
        });
    }
    
    // Function to update pin button appearance
    function updatePinButton(button, isPinned) {
        button.dataset.pinned = isPinned;
        button.classList.toggle('btn-warning', isPinned);
        button.classList.toggle('btn-outline-warning', !isPinned);
        
        // Update tooltip title
        button.setAttribute('title', isPinned ? 'Unpin this tournament' : 'Pin this tournament');
        
        // Update icon
        const icon = button.querySelector('i');
        if (icon) {
            icon.className = isPinned ? 'fas fa-thumbtack' : 'fas fa-thumbtack';
        }
    }
    
    // Function to sort tournaments with pinned ones first
    function sortTournaments() {
        const container = document.getElementById('tournamentsContainer');
        if (!container) return;
        
        const pinnedKey = `pinned_tournaments_${getUserId()}`;
        const pinnedTournaments = JSON.parse(sessionStorage.getItem(pinnedKey) || '[]');
        
        // Convert NodeList to array for sorting
        const cards = Array.from(container.querySelectorAll('.tournament-card'));
        
        // Sort cards - pinned first, then by date (newest first)
        cards.sort((a, b) => {
            const aId = parseInt(a.dataset.tournamentId);
            const bId = parseInt(b.dataset.tournamentId);
            const aIsPinned = pinnedTournaments.includes(aId);
            const bIsPinned = pinnedTournaments.includes(bId);
            
            // Pinned tournaments first
            if (aIsPinned && !bIsPinned) return -1;
            if (!aIsPinned && bIsPinned) return 1;
            
            // Then sort by date (newest first)
            const aDate = new Date(a.dataset.startDate || a.dataset.createdAt);
            const bDate = new Date(b.dataset.startDate || b.dataset.createdAt);
            return bDate - aDate;
        });
        
        // Re-append cards in new order
        cards.forEach(card => {
            container.appendChild(card.parentElement);
        });
    }
    
    // Helper function to get CSRF token
    function getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || '';
    }
    
    // Helper function to get user ID
    function getUserId() {
        return document.body.dataset.userId || '';
    }
    
    // Helper function to show toast notifications
    function showToast(title, message, type = 'info') {
        const toastContainer = document.getElementById('toastContainer');
        if (!toastContainer) return;
        
        const toastId = 'toast-' + Date.now();
        const toastHtml = `
            <div id="${toastId}" class="toast align-items-center text-white bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <strong>${title}</strong><br>${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            </div>
        `;
        
        const toastElement = document.createElement('div');
        toastElement.innerHTML = toastHtml;
        const toast = toastElement.firstElementChild;
        toastContainer.appendChild(toast);
        
        const bsToast = new bootstrap.Toast(toast, { autohide: true, delay: 3000 });
        bsToast.show();
        
        // Remove toast after it's hidden
        toast.addEventListener('hidden.bs.toast', function() {
            toast.remove();
        });
    }
});
