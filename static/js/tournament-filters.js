document.addEventListener('DOMContentLoaded', function() {
    // Get DOM elements
    const searchInput = document.getElementById('searchInput');
    const statusFilter = document.getElementById('statusFilter');
    const sortBy = document.getElementById('sortBy');
    const resetBtn = document.getElementById('resetFilters');
    const tournamentsContainer = document.getElementById('tournamentsContainer');
    
    // Store original tournament data
    let tournaments = [];
    
    // Initialize the filter functionality
    function initFilters() {
        // Get all tournament cards
        const tournamentCards = document.querySelectorAll('.tournament-card');
        
        // Store original data for each tournament
        tournaments = Array.from(tournamentCards).map(card => {
            const titleElement = card.querySelector('.card-title') || {};
            return {
                element: card,
                name: titleElement.textContent ? titleElement.textContent.toLowerCase() : '',
                status: card.getAttribute('data-status') || 'upcoming',
                startDate: card.getAttribute('data-start-date') || '',
                createdAt: card.getAttribute('data-created-at') || ''
            };
        });
        
        // Debug: Log the tournaments data
        console.log('Initialized tournaments:', tournaments);
        
        // Add event listeners
        searchInput.addEventListener('input', filterTournaments);
        statusFilter.addEventListener('change', filterTournaments);
        sortBy.addEventListener('change', sortTournaments);
        resetBtn.addEventListener('click', resetFilters);
        
        // Initial filter and sort
        filterAndSort();
    }
    
    // Filter tournaments based on search and status
    function filterTournaments() {
        const searchTerm = searchInput.value.toLowerCase();
        const status = statusFilter.value.toLowerCase();
        
        // Debug: Log filter criteria
        console.log('Filtering with:', { searchTerm, status });
        
        let visibleCount = 0;
        
        tournaments.forEach(tournament => {
            const cardText = tournament.element.textContent.toLowerCase();
            const matchesSearch = searchTerm === '' || 
                                tournament.name.includes(searchTerm) || 
                                cardText.includes(searchTerm);
            
            // Normalize status values for comparison
            let tournamentStatus = tournament.status ? tournament.status.toLowerCase() : '';
            // Map 'in_progress' to 'ongoing' for backward compatibility
            if (tournamentStatus === 'in_progress') tournamentStatus = 'ongoing';
            
            const matchesStatus = status === 'all' || tournamentStatus === status;
            
            const shouldShow = matchesSearch && matchesStatus;
            
            if (shouldShow) {
                tournament.element.closest('.col-12').style.display = '';
                visibleCount++;
            } else {
                tournament.element.closest('.col-12').style.display = 'none';
            }
            
            // Debug: Log visibility for each tournament
            console.log('Tournament:', {
                name: tournament.name,
                status: tournamentStatus,
                matchesSearch,
                matchesStatus,
                shouldShow
            });
        });
        
        // Re-apply sorting after filtering
        sortTournaments();
    }
    
    // Sort tournaments based on selected criteria
    function sortTournaments() {
        const sortValue = sortBy.value;
        const container = document.querySelector('#tournamentsContainer');
        if (!container) {
            console.error('Could not find tournaments container');
            return;
        }

        // Get all tournament cards that are currently visible
        const tournamentCards = Array.from(document.querySelectorAll('.tournament-card'));
        const visibleTournaments = tournaments.filter(t => {
            const col = t.element.closest('.col-12');
            return col && window.getComputedStyle(col).display !== 'none';
        });

        // Sort the tournaments array based on the selected criteria
        visibleTournaments.sort((a, b) => {
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
                default:
                    return 0;
            }
        });

        // Get the parent row element
        const row = container.querySelector('.row');
        if (!row) return;

        // Clear the current content
        const fragment = document.createDocumentFragment();
        
        // Create a map of tournament IDs to their column elements for quick lookup
        const columnsMap = new Map();
        const columns = Array.from(row.children);
        columns.forEach(col => {
            const card = col.querySelector('.tournament-card');
            if (card) {
                const id = card.getAttribute('data-tournament-id');
                if (id) columnsMap.set(id, col);
            }
        });

        // Append columns in the new order
        visibleTournaments.forEach(tournament => {
            const col = columnsMap.get(tournament.element.getAttribute('data-tournament-id'));
            if (col) {
                fragment.appendChild(col);
            }
        });

        // Clear and repopulate the row
        while (row.firstChild) {
            row.removeChild(row.firstChild);
        }
        row.appendChild(fragment);
        
        // Sort based on selected criteria
        visibleTournaments.sort((a, b) => {
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
                default:
                    return 0;
            }
        });
        
        // Reorder DOM elements
        visibleTournaments.forEach(tournament => {
            container.appendChild(tournament.element.parentElement);
        });
    }
    
    // Reset all filters and sorting
    function resetFilters() {
        searchInput.value = '';
        statusFilter.value = 'all';
        sortBy.value = 'recent';
        filterAndSort();
    }
    
    // Apply both filtering and sorting
    function filterAndSort() {
        filterTournaments();
        sortTournaments();
    }
    
    // Initialize the filters after a short delay to ensure DOM is fully loaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFilters);
    } else {
        // If DOM is already loaded, initialize immediately
        setTimeout(initFilters, 100);
    }
});
