document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const searchInput = document.getElementById('searchInput');
    const statusFilter = document.getElementById('statusFilter');
    const sortBy = document.getElementById('sortBy');
    const resetBtn = document.getElementById('resetFilters');
    const tournamentsContainer = document.getElementById('tournamentsContainer');
    
    if (!tournamentsContainer) {
        console.error('Tournaments container not found');
        return;
    }

    // Initialize the filter functionality
    function initFilters() {
        console.log('Initializing tournament filters...');
        
        // Add event listeners
        if (searchInput) searchInput.addEventListener('input', filterAndSort);
        if (statusFilter) statusFilter.addEventListener('change', filterAndSort);
        if (sortBy) sortBy.addEventListener('change', sortTournaments);
        if (resetBtn) resetBtn.addEventListener('click', resetFilters);
        
        // Initial filter and sort
        filterAndSort();
    }
    
    // Get all tournament cards with their data
    function getTournamentElements() {
        const cards = document.querySelectorAll('.tournament-card');
        return Array.from(cards).map(card => {
            const playerCountEl = card.querySelector('[data-player-count]');
            return {
                element: card,
                name: card.getAttribute('data-name') || card.querySelector('.card-title')?.textContent?.trim() || '',
                status: card.getAttribute('data-status') || 'upcoming',
                startDate: card.getAttribute('data-start-date') || '',
                createdAt: card.getAttribute('data-created-at') || '',
                location: card.getAttribute('data-location') || '',
                playerCount: playerCountEl ? parseInt(playerCountEl.textContent) || 0 : 0,
                tournamentId: card.getAttribute('data-tournament-id') || ''
            };
        });
    }
    
    // Filter tournaments based on search and status
    function filterTournaments() {
        const searchTerm = searchInput ? searchInput.value.toLowerCase() : '';
        const status = statusFilter ? statusFilter.value.toLowerCase() : 'all';
        
        console.log('Filtering tournaments:', { searchTerm, status });
        
        const tournaments = getTournamentElements();
        let visibleCount = 0;
        
        tournaments.forEach(tournament => {
            const cardElement = tournament.element;
            const cardText = cardElement.textContent.toLowerCase();
            
            // Check search term
            const matchesSearch = searchTerm === '' || 
                                tournament.name.toLowerCase().includes(searchTerm) ||
                                tournament.location.toLowerCase().includes(searchTerm) ||
                                cardText.includes(searchTerm);
            
            // Check status
            let tournamentStatus = tournament.status ? tournament.status.toLowerCase() : '';
            if (tournamentStatus === 'in_progress') tournamentStatus = 'ongoing';
            const matchesStatus = status === 'all' || tournamentStatus === status;
            
            // Show/hide based on filters
            const shouldShow = matchesSearch && matchesStatus;
            const parentCol = cardElement.closest('.col-12');
            
            if (parentCol) {
                parentCol.style.display = shouldShow ? '' : 'none';
                if (shouldShow) visibleCount++;
            } else {
                console.warn('Could not find parent column for tournament card');
            }
        });
        
        console.log(`Filtering complete. ${visibleCount} tournaments visible.`);
        return visibleCount > 0;
    }
    
    // Sort tournaments based on selected criteria
    function sortTournaments() {
        const sortValue = sortBy ? sortBy.value : 'recent';
        console.log('Sorting tournaments by:', sortValue);
        
        const container = document.getElementById('tournamentsContainer');
        if (!container) {
            console.error('Could not find tournaments container');
            return;
        }

        // Get all tournament columns that are visible
        const tournamentCols = Array.from(container.children).filter(col => {
            return col.classList.contains('col-12') && 
                   window.getComputedStyle(col).display !== 'none';
        });

        if (tournamentCols.length === 0) {
            console.log('No visible tournaments to sort');
            return;
        }

        // Sort the columns based on the selected criteria
        tournamentCols.sort((colA, colB) => {
            const cardA = colA.querySelector('.tournament-card');
            const cardB = colB.querySelector('.tournament-card');
            
            if (!cardA || !cardB) return 0;
            
            const getCardData = (card) => {
                const playerCountEl = card.querySelector('[data-player-count]');
                return {
                    name: card.getAttribute('data-name') || '',
                    startDate: card.getAttribute('data-start-date') || '',
                    createdAt: card.getAttribute('data-created-at') || '',
                    playerCount: playerCountEl ? parseInt(playerCountEl.textContent) || 0 : 0
                };
            };
            
            const a = getCardData(cardA);
            const b = getCardData(cardB);
            
            switch (sortValue) {
                case 'recent':
                    return new Date(b.createdAt) - new Date(a.createdAt);
                case 'oldest':
                    return new Date(a.createdAt) - new Date(b.createdAt);
                case 'name_asc':
                    return a.name.localeCompare(b.name);
                case 'name_desc':
                    return b.name.localeCompare(a.name);
                case 'start_date':
                    return new Date(a.startDate) - new Date(b.startDate);
                case 'players_asc':
                    return a.playerCount - b.playerCount;
                case 'players_desc':
                    return b.playerCount - a.playerCount;
                default:
                    return 0;
            }
        });

        // Reorder the DOM
        const fragment = document.createDocumentFragment();
        tournamentCols.forEach(col => fragment.appendChild(col));
        container.appendChild(fragment);
        
        console.log('Tournaments sorted successfully');
    }
    
    // Reset all filters and sorting
    function resetFilters() {
        console.log('Resetting filters...');
        if (searchInput) searchInput.value = '';
        if (statusFilter) statusFilter.value = 'all';
        if (sortBy) sortBy.value = 'recent';
        filterAndSort();
    }
    
    // Apply both filtering and sorting
    function filterAndSort() {
        console.log('Applying filters and sorting...');
        const hasVisible = filterTournaments();
        if (hasVisible) {
            sortTournaments();
        }
    }
    
    // Initialize the filters
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFilters);
    } else {
        // If DOM is already loaded, initialize after a short delay
        // to ensure all elements are available
        setTimeout(initFilters, 100);
    }
});
