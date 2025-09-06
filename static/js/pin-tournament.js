/**
 * Handles pin/unpin functionality for tournaments
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize pinned filter state
    let showPinnedOnly = false;
    const filterPinnedBtn = document.getElementById('filterPinned');
    
    // Initial sort when page loads
    setTimeout(sortTournaments, 100); // Small delay to ensure DOM is fully loaded
    
    // Toggle pinned filter
    console.log('Initializing pinned filter button...');
    if (filterPinnedBtn) {
        console.log('Filter button found, adding click handler');
        filterPinnedBtn.addEventListener('click', function(e) {
            console.log('Filter button clicked');
            showPinnedOnly = !showPinnedOnly;
            console.log('showPinnedOnly set to:', showPinnedOnly);
            updatePinnedFilterButton();
            filterTournaments();
        });
    } else {
        console.error('Could not find filterPinnedBtn element');
    }
    
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
                
                // Sort tournaments to ensure pinned ones are at the top and apply filter
                setTimeout(() => {
                    sortTournaments();
                    if (showPinnedOnly) {
                        filterTournaments();
                    }
                }, 0); // Small delay to ensure DOM updates are processed
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
    
    // Function to update pinned filter button state
    function updatePinnedFilterButton() {
        if (!filterPinnedBtn) return;
        
        if (showPinnedOnly) {
            filterPinnedBtn.classList.remove('btn-outline-warning');
            filterPinnedBtn.classList.add('btn-warning');
            filterPinnedBtn.title = 'Showing pinned tournaments only. Click to show all.';
        } else {
            filterPinnedBtn.classList.remove('btn-warning');
            filterPinnedBtn.classList.add('btn-outline-warning');
            filterPinnedBtn.title = 'Show only pinned tournaments';
        }
    }
    
    // Function to filter tournaments based on pinned status
    function filterTournaments() {
        console.log('filterTournaments called, showPinnedOnly:', showPinnedOnly);
        const container = document.getElementById('tournamentsContainer');
        if (!container) {
            console.error('Could not find tournamentsContainer');
            return;
        }
        
        const pinnedKey = `pinned_tournaments_${getUserId()}`;
        const pinnedTournaments = JSON.parse(sessionStorage.getItem(pinnedKey) || '[]');
        
        // Get all tournament card containers (the col-* divs)
        const tournamentContainers = container.querySelectorAll('.col-12.col-md-6.col-lg-4.mb-4');
        console.log('Found', tournamentContainers.length, 'tournament containers');
        
        tournamentContainers.forEach(container => {
            const card = container.querySelector('.tournament-card');
            if (!card) {
                console.log('No card found in container');
                return;
            }
            
            const tournamentId = parseInt(card.dataset.tournamentId);
            if (isNaN(tournamentId)) {
                console.log('Invalid tournament ID for card:', card);
                return;
            }
            
            const isPinned = pinnedTournaments.includes(tournamentId);
            console.log(`Tournament ${tournamentId} isPinned:`, isPinned);
            
            if (showPinnedOnly && !isPinned) {
                console.log(`Hiding tournament ${tournamentId}`);
                container.style.display = 'none';
            } else {
                console.log(`Showing tournament ${tournamentId}`);
                container.style.display = '';
            }
        });
    }
    
    // Function to sort tournaments with pinned ones first
    function sortTournaments() {
        const container = document.getElementById('tournamentsContainer');
        if (!container) {
            console.error('Tournaments container not found');
            return;
        }
        
        const pinnedKey = `pinned_tournaments_${getUserId()}`;
        const pinnedTournaments = JSON.parse(sessionStorage.getItem(pinnedKey) || '[]');
        
        // Get all tournament container elements
        const tournamentContainers = Array.from(container.querySelectorAll('.col-12.col-md-6.col-lg-4.mb-4'));
        
        // Sort containers based on pinned status and date
        tournamentContainers.sort((a, b) => {
            const cardA = a.querySelector('.tournament-card');
            const cardB = b.querySelector('.tournament-card');
            
            if (!cardA || !cardB) return 0;
            
            const aId = parseInt(cardA.dataset.tournamentId);
            const bId = parseInt(cardB.dataset.tournamentId);
            const aIsPinned = pinnedTournaments.includes(aId);
            const bIsPinned = pinnedTournaments.includes(bId);
            
            // Pinned tournaments first
            if (aIsPinned && !bIsPinned) return -1;
            if (!aIsPinned && bIsPinned) return 1;
            
            // Then sort by date (newest first)
            const aDate = new Date(cardA.dataset.startDate || cardA.dataset.createdAt || 0);
            const bDate = new Date(cardB.dataset.startDate || cardB.dataset.createdAt || 0);
            return bDate - aDate;
        });
        
        // Re-append containers in new order
        tournamentContainers.forEach(container => {
            container.parentNode.appendChild(container);
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
