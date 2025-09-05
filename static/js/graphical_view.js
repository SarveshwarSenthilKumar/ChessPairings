// Initialize the graphical view
function initGraphicalView(tournamentData) {
    // DOM elements
    const visualizationEl = document.getElementById('visualization');
    const viewModeSelect = document.getElementById('viewMode');
    const filterPlayerSelect = document.getElementById('filterPlayer');
    const filterRoundSelect = document.getElementById('filterRound');
    const resetFiltersBtn = document.getElementById('resetFilters');
    const showPlayerLabels = document.getElementById('showPlayerLabels');
    const zoomInBtn = document.getElementById('zoomIn');
    const zoomOutBtn = document.getElementById('zoomOut');
    const fitAllBtn = document.getElementById('fitAll');
    const tooltip = document.getElementById('tooltip');
    
    // Initialize timeline container
    const container = document.getElementById('visualization');
    
    // Process data for visualization
    const { items, groups, playerPositions } = processTournamentData(tournamentData);
    
    // Initialize timeline
    const timeline = new vis.Timeline(container, new vis.DataSet(items), groups, {
        start: new Date(tournamentData.startDate),
        end: new Date(tournamentData.endDate),
        orientation: 'top',
        showCurrentTime: false,
        zoomable: true,
        moveable: true,
        selectable: true,
        multiselect: true,
        stack: true,
        showMajorLabels: true,
        showTooltips: false, // We'll handle tooltips manually
        groupOrder: 'content',
        margin: {
            item: {
                horizontal: 0,
                vertical: 10
            },
            axis: 5
        },
        format: {
            minorLabels: {
                minute: 'h:mma',
                hour: 'ha',
                weekday: 'ddd',
                day: 'D',
                month: 'MMM',
                year: 'YYYY'
            },
            majorLabels: {
                minute: 'ddd, MMM D',
                hour: 'ddd, MMM D',
                weekday: 'MMMM YYYY',
                day: 'MMMM YYYY',
                month: 'YYYY',
                year: ''
            }
        },
        min: new Date(tournamentData.startDate),
        max: new Date(tournamentData.endDate),
        zoomMin: 1000 * 60 * 60 * 24 * 1, // 1 day
        zoomMax: 1000 * 60 * 60 * 24 * 365, // 1 year
        groupHeightMode: 'fixed',
        timeAxis: { scale: 'day', step: 1 },
        rollingMode: {
            follow: true,
            offset: 0.5
        },
        showTooltips: true,
        tooltip: {
            followMouse: true,
            overflowMethod: 'cap'
        },
        tooltipOnItemUpdateTime: true
    });
    
    // Store player rows for highlighting
    const playerRows = document.querySelectorAll('.player-row');
    
    // Highlight player row on timeline item hover
    timeline.on('select', function(properties) {
        // Remove highlight from all rows
        playerRows.forEach(row => row.classList.remove('table-active'));
        
        // Highlight selected rows
        properties.items.forEach(itemId => {
            const item = items.find(i => i.id === itemId);
            if (item && item.playerId) {
                const row = document.querySelector(`.player-row[data-player-id="${item.playerId}"]`);
                if (row) row.classList.add('table-active');
            }
        });
    });
    
    // Handle mouse over timeline items
    timeline.on('itemover', function(properties) {
        const item = items.find(i => i.id === properties.item);
        if (!item) return;
        
        // Show tooltip
        tooltip.style.display = 'block';
        tooltip.innerHTML = formatTooltipContent(item, tournamentData);
        
        // Position tooltip
        const rect = container.getBoundingClientRect();
        tooltip.style.left = (properties.event.clientX - rect.left) + 'px';
        tooltip.style.top = (properties.event.clientY - rect.top - 40) + 'px';
        
        // Highlight related items (games between same players)
        if (item.type === 'game') {
            const relatedItems = items.filter(i => 
                i.type === 'game' && 
                ((i.player1Id === item.player1Id && i.player2Id === item.player2Id) || 
                 (i.player1Id === item.player2Id && i.player2Id === item.player1Id))
            );
            
            timeline.setSelection(relatedItems.map(i => i.id));
        }
    });
    
    // Handle mouse out of timeline items
    timeline.on('itemout', function() {
        tooltip.style.display = 'none';
        timeline.setSelection([]);
    });
    
    // Handle mouse move for tooltip following
    container.addEventListener('mousemove', function(event) {
        if (tooltip.style.display === 'block') {
            const rect = container.getBoundingClientRect();
            tooltip.style.left = (event.clientX - rect.left + 10) + 'px';
            tooltip.style.top = (event.clientY - rect.top - 40) + 'px';
        }
    });
    
    // Handle view mode changes
    viewModeSelect.addEventListener('change', function() {
        updateViewMode(timeline, items, groups, playerPositions, tournamentData, this.value);
    });
    
    // Handle player filter
    filterPlayerSelect.addEventListener('change', function() {
        applyFilters(timeline, items, groups, playerPositions, tournamentData);
    });
    
    // Handle round filter
    filterRoundSelect.addEventListener('change', function() {
        applyFilters(timeline, items, groups, playerPositions, tournamentData);
    });
    
    // Reset filters
    resetFiltersBtn.addEventListener('click', function() {
        filterPlayerSelect.value = '';
        filterRoundSelect.value = '';
        applyFilters(timeline, items, groups, playerPositions, tournamentData);
    });
    
    // Toggle player labels
    showPlayerLabels.addEventListener('change', function() {
        const labels = document.querySelectorAll('.player-label');
        labels.forEach(label => {
            label.style.visibility = this.checked ? 'visible' : 'hidden';
        });
    });
    
    // Zoom controls
    zoomInBtn.addEventListener('click', function() {
        const range = timeline.getWindow();
        const interval = range.end - range.start;
        const newInterval = interval * 0.7; // Zoom in by 30%
        const center = range.start.getTime() + interval / 2;
        timeline.setWindow(
            new Date(center - newInterval / 2),
            new Date(center + newInterval / 2)
        );
    });
    
    zoomOutBtn.addEventListener('click', function() {
        const range = timeline.getWindow();
        const interval = range.end - range.start;
        const newInterval = interval / 0.7; // Zoom out by 30%
        const center = range.start.getTime() + interval / 2;
        
        // Ensure we don't zoom out beyond the tournament dates
        const minStart = new Date(tournamentData.startDate).getTime();
        const maxEnd = new Date(tournamentData.endDate).getTime();
        const newStart = Math.max(minStart, center - newInterval / 2);
        const newEnd = Math.min(maxEnd, center + newInterval / 2);
        
        timeline.setWindow(new Date(newStart), new Date(newEnd));
    });
    
    // Fit all button
    fitAllBtn.addEventListener('click', function() {
        timeline.fit({
            min: new Date(tournamentData.startDate),
            max: new Date(tournamentData.endDate)
        }, { animation: true });
    });
    
    // Initial view setup
    updateViewMode(timeline, items, groups, playerPositions, tournamentData, 'timeline');
    
    // Add player labels if enabled
    if (showPlayerLabels.checked) {
        addPlayerLabels(playerPositions, container);
    }
    
    // Handle window resize
    window.addEventListener('resize', function() {
        timeline.redraw();
        if (showPlayerLabels.checked) {
            removePlayerLabels();
            addPlayerLabels(playerPositions, container);
        }
    });
    
    // Handle timeline redraw to update player labels
    timeline.on('changed', function() {
        if (showPlayerLabels.checked) {
            removePlayerLabels();
            addPlayerLabels(playerPositions, container);
        }
    });
}

// Process tournament data for the timeline
function processTournamentData(tournamentData) {
    const items = [];
    const groups = [];
    const playerPositions = {};
    
    // Create groups for players
    tournamentData.players.forEach((player, index) => {
        const groupId = `player-${player.id}`;
        groups.push({
            id: groupId,
            content: player.name,
            value: index + 1,
            className: 'player-group'
        });
        
        // Store player position for labels
        playerPositions[player.id] = {
            id: groupId,
            name: player.name,
            rating: player.rating || 'Unrated',
            index: index
        };
        
        // Add player's games
        if (tournamentData.roundsData && tournamentData.roundsData[player.id]) {
            tournamentData.roundsData[player.id].forEach(game => {
                if (!game) return;
                
                const gameId = `game-${player.id}-${game.opponentId}-${game.round}`;
                const isBye = game.opponentId === null;
                
                // Skip if this game was already added (to avoid duplicates)
                if (items.some(item => item.id === gameId)) return;
                
                // Determine game result and styling
                let className = 'ongoing';
                let title = 'Game in progress';
                
                if (isBye) {
                    className = 'win';
                    title = 'Bye';
                } else if (game.result !== null) {
                    if (game.result === 1) {
                        className = 'win';
                        title = 'Win';
                    } else if (game.result === 0.5) {
                        className = 'draw';
                        title = 'Draw';
                    } else if (game.result === 0) {
                        className = 'loss';
                        title = 'Loss';
                    }
                }
                
                // Add game to items
                items.push({
                    id: gameId,
                    group: groupId,
                    content: isBye ? 'BYE' : `vs ${game.opponentName} (${game.opponentRating || 'Unrated'})`,
                    start: game.date || new Date(tournamentData.startDate).setDate(
                        new Date(tournamentData.startDate).getDate() + (game.round - 1) * 2
                    ),
                    end: game.date ? 
                        new Date(new Date(game.date).getTime() + 1000 * 60 * 90) : // 1.5 hours per game
                        new Date(new Date(tournamentData.startDate).setDate(
                            new Date(tournamentData.startDate).getDate() + (game.round - 1) * 2 + 0.5
                        )),
                    type: isBye ? 'bye' : 'game',
                    className: className,
                    title: title,
                    round: game.round,
                    playerId: player.id,
                    player1Id: player.id,
                    player2Id: game.opponentId,
                    result: game.result,
                    color: getResultColor(game.result, isBye)
                });
            });
        }
    });
    
    // Sort items by start time
    items.sort((a, b) => new Date(a.start) - new Date(b.start));
    
    return { items, groups, playerPositions };
}

// Get color based on game result
function getResultColor(result, isBye = false) {
    if (isBye) return '#6c757d'; // Gray for byes
    
    switch (result) {
        case 1: return '#28a745'; // Green for win
        case 0.5: return '#ffc107'; // Yellow for draw
        case 0: return '#dc3545'; // Red for loss
        default: return '#6c757d'; // Gray for ongoing
    }
}

// Format tooltip content for a game
function formatTooltipContent(item, tournamentData) {
    if (item.type === 'bye') {
        return `
            <div class="text-center">
                <h6 class="mb-2">Round ${item.round}: Bye</h6>
                <div class="small text-muted">
                    ${new Date(item.start).toLocaleDateString()}
                </div>
            </div>
        `;
    }
    
    const player1 = tournamentData.players.find(p => p.id === item.player1Id);
    const player2 = tournamentData.players.find(p => p.id === item.player2Id);
    
    if (!player1 || !player2) return '';
    
    let resultText = 'vs';
    if (item.result === 1) resultText = '1-0';
    else if (item.result === 0) resultText = '0-1';
    else if (item.result === 0.5) resultText = '½-½';
    
    return `
        <div class="text-center">
            <h6 class="mb-2">Round ${item.round}: ${player1.name} ${resultText} ${player2.name}</h6>
            <div class="small text-muted">
                ${new Date(item.start).toLocaleString()} - ${new Date(item.end).toLocaleTimeString()}
            </div>
            <div class="mt-2">
                <span class="badge ${getResultBadgeClass(item.result)}">
                    ${item.title}
                </span>
            </div>
        </div>
    `;
}

// Get badge class based on result
function getResultBadgeClass(result) {
    switch (result) {
        case 1: return 'bg-success';
        case 0.5: return 'bg-warning text-dark';
        case 0: return 'bg-danger';
        default: return 'bg-secondary';
    }
}

// Update view mode (timeline, bracket, standings)
function updateViewMode(timeline, items, groups, playerPositions, tournamentData, mode) {
    // Remove any existing custom elements
    removePlayerLabels();
    
    // Update timeline options based on view mode
    const options = {
        orientation: 'top',
        showCurrentTime: false,
        zoomable: true,
        moveable: true,
        selectable: true,
        multiselect: true,
        stack: true,
        showMajorLabels: true,
        showTooltips: false,
        groupOrder: 'content',
        margin: {
            item: {
                horizontal: 0,
                vertical: 10
            },
            axis: 5
        },
        format: {
            minorLabels: {
                minute: 'h:mma',
                hour: 'ha',
                weekday: 'ddd',
                day: 'D',
                month: 'MMM',
                year: 'YYYY'
            },
            majorLabels: {
                minute: 'ddd, MMM D',
                hour: 'ddd, MMM D',
                weekday: 'MMMM YYYY',
                day: 'MMMM YYYY',
                month: 'YYYY',
                year: ''
            }
        },
        min: new Date(tournamentData.startDate),
        max: new Date(tournamentData.endDate),
        zoomMin: 1000 * 60 * 60 * 24 * 1, // 1 day
        zoomMax: 1000 * 60 * 60 * 24 * 365, // 1 year
        groupHeightMode: 'fixed',
        timeAxis: { scale: 'day', step: 1 },
        tooltip: {
            followMouse: true,
            overflowMethod: 'cap'
        },
        tooltipOnItemUpdateTime: true
    };
    
    switch (mode) {
        case 'bracket':
            // For bracket view, we'll show a simplified view of the tournament
            options.orientation = 'top';
            options.stack = false;
            options.verticalScroll = true;
            options.horizontalScroll = true;
            options.zoomKey = 'ctrlKey';
            options.timeAxis = { scale: 'day', step: 1 };
            
            // Process items for bracket view
            const bracketItems = processBracketData(tournamentData);
            timeline.setItems(bracketItems.items);
            timeline.setGroups(bracketItems.groups);
            break;
            
        case 'standings':
            // For standings view, we'll show player performance over time
            options.orientation = 'top';
            options.stack = false;
            options.showMajorLabels = true;
            options.timeAxis = { scale: 'day', step: 1 };
            
            // Process items for standings view
            const standingsItems = processStandingsData(tournamentData);
            timeline.setItems(standingsItems.items);
            timeline.setGroups(standingsItems.groups);
            break;
            
        case 'timeline':
        default:
            // Default timeline view
            timeline.setItems(items);
            timeline.setGroups(groups);
            break;
    }
    
    // Apply the options
    timeline.setOptions(options);
    
    // Redraw the timeline
    timeline.redraw();
    
    // Add player labels if enabled
    if (document.getElementById('showPlayerLabels').checked) {
        addPlayerLabels(playerPositions, document.getElementById('visualization'));
    }
}

// Process data for bracket view
function processBracketData(tournamentData) {
    const items = [];
    const groups = [];
    
    // Group games by round
    const rounds = {};
    
    // Process each player's games
    tournamentData.players.forEach(player => {
        if (!tournamentData.roundsData[player.id]) return;
        
        tournamentData.roundsData[player.id].forEach(game => {
            if (!game) return;
            
            const gameId = `game-${player.id}-${game.opponentId || 'bye'}-${game.round}`;
            
            // Skip if this game was already added
            if (items.some(item => item.id === gameId)) return;
            
            // Get opponent info
            const opponent = game.opponentId ? 
                tournamentData.players.find(p => p.id === game.opponentId) : 
                null;
            
            // Determine game result and styling
            let className = 'ongoing';
            let title = 'Game in progress';
            
            if (!game.opponentId) {
                className = 'win';
                title = 'Bye';
            } else if (game.result !== null) {
                if (game.result === 1) {
                    className = 'win';
                    title = 'Win';
                } else if (game.result === 0.5) {
                    className = 'draw';
                    title = 'Draw';
                } else if (game.result === 0) {
                    className = 'loss';
                    title = 'Loss';
                }
            }
            
            // Add game to items
            items.push({
                id: gameId,
                group: `round-${game.round}`,
                content: game.opponentId ? 
                    `${player.name} vs ${opponent.name}` : 
                    `${player.name} - BYE`,
                start: game.date || new Date(tournamentData.startDate).setDate(
                    new Date(tournamentData.startDate).getDate() + (game.round - 1) * 2
                ),
                end: game.date ? 
                    new Date(new Date(game.date).getTime() + 1000 * 60 * 90) : // 1.5 hours per game
                    new Date(new Date(tournamentData.startDate).setDate(
                        new Date(tournamentData.startDate).getDate() + (game.round - 1) * 2 + 0.5
                    )),
                type: game.opponentId ? 'game' : 'bye',
                className: className,
                title: title,
                round: game.round,
                player1Id: player.id,
                player2Id: game.opponentId,
                result: game.result,
                color: getResultColor(game.result, !game.opponentId)
            });
            
            // Ensure round group exists
            if (!rounds[`round-${game.round}`]) {
                rounds[`round-${game.round}`] = {
                    id: `round-${game.round}`,
                    content: `Round ${game.round}`,
                    nestedGroups: [],
                    showNested: true
                };
            }
        });
    });
    
    // Convert rounds object to array
    Object.values(rounds).forEach(round => {
        groups.push(round);
    });
    
    return { items, groups };
}

// Process data for standings view
function processStandingsData(tournamentData) {
    const items = [];
    const groups = [];
    
    // Track player standings over time
    const playerStandings = {};
    const rounds = [];
    
    // Initialize player standings
    tournamentData.players.forEach(player => {
        playerStandings[player.id] = {
            name: player.name,
            points: 0,
            history: []
        };
    });
    
    // Process each round
    for (let round = 1; round <= tournamentData.rounds; round++) {
        const roundDate = new Date(tournamentData.startDate);
        roundDate.setDate(roundDate.getDate() + (round - 1) * 2);
        
        // Process each player's game in this round
        tournamentData.players.forEach(player => {
            if (!tournamentData.roundsData[player.id]) return;
            
            const game = tournamentData.roundsData[player.id].find(g => g && g.round === round);
            if (!game) return;
            
            // Update player's points based on game result
            if (game.result !== null) {
                playerStandings[player.id].points += game.result;
            }
            
            // Record standing after this round
            playerStandings[player.id].history.push({
                round: round,
                date: roundDate,
                points: playerStandings[player.id].points,
                game: game
            });
        });
        
        // Add round to rounds array
        rounds.push({
            id: `round-${round}`,
            content: `Round ${round}`,
            start: roundDate,
            end: new Date(roundDate.getTime() + 1000 * 60 * 60 * 24), // 1 day per round
            type: 'background',
            className: 'round-background',
            group: 'rounds'
        });
    }
    
    // Create groups for players
    tournamentData.players.forEach((player, index) => {
        const groupId = `player-${player.id}`;
        groups.push({
            id: groupId,
            content: player.name,
            value: index + 1,
            className: 'player-group'
        });
        
        // Add points over time for this player
        if (playerStandings[player.id] && playerStandings[player.id].history.length > 0) {
            playerStandings[player.id].history.forEach((standing, i) => {
                items.push({
                    id: `standing-${player.id}-${standing.round}`,
                    group: groupId,
                    x: standing.date,
                    y: standing.points,
                    content: standing.points.toFixed(1),
                    title: `${player.name}: ${standing.points} points after round ${standing.round}`,
                    className: 'data-point',
                    points: standing.points,
                    round: standing.round
                });
                
                // Add line to next point if there is one
                if (i < playerStandings[player.id].history.length - 1) {
                    const nextStanding = playerStandings[player.id].history[i + 1];
                    items.push({
                        id: `line-${player.id}-${standing.round}`,
                        group: groupId,
                        type: 'range',
                        start: standing.date,
                        end: nextStanding.date,
                        content: '',
                        className: 'trend-line',
                        style: `background-color: ${getPlayerColor(index)};`
                    });
                }
            });
        }
    });
    
    // Add round background items
    items.push(...rounds);
    
    // Add rounds group
    groups.unshift({
        id: 'rounds',
        content: 'Rounds',
        visible: false,
        showNested: false
    });
    
    return { items, groups };
}

// Get a unique color for each player
function getPlayerColor(index) {
    const colors = [
        '#4e79a7', '#f28e2c', '#e15759', '#76b7b2', '#59a14f',
        '#edc949', '#af7aa1', '#ff9da7', '#9c755f', '#bab0ab',
        '#8cd17d', '#499894', '#86bcb6', '#e15759', '#79706e',
        '#d37295', '#b07aa1', '#d4a6c8', '#9d7660', '#d7b5a6'
    ];
    return colors[index % colors.length];
}

// Apply filters to the timeline
function applyFilters(timeline, items, groups, playerPositions, tournamentData) {
    const playerFilter = document.getElementById('filterPlayer').value;
    const roundFilter = document.getElementById('filterRound').value;
    const viewMode = document.getElementById('viewMode').value;
    
    // Get the current view mode function
    let processFunction;
    switch (viewMode) {
        case 'bracket':
            processFunction = processBracketData;
            break;
        case 'standings':
            processFunction = processStandingsData;
            break;
        case 'timeline':
        default:
            processFunction = (data) => ({ items, groups });
            break;
    }
    
    // Process the data
    const processedData = processFunction(tournamentData);
    let filteredItems = [...processedData.items];
    let filteredGroups = [...processedData.groups];
    
    // Apply player filter
    if (playerFilter) {
        filteredItems = filteredItems.filter(item => {
            return item.player1Id == playerFilter || item.player2Id == playerFilter;
        });
        
        // Only show groups that have items
        const groupIdsWithItems = new Set(filteredItems.map(item => item.group));
        filteredGroups = filteredGroups.filter(group => groupIdsWithItems.has(group.id));
    }
    
    // Apply round filter
    if (roundFilter) {
        filteredItems = filteredItems.filter(item => {
            return item.round == roundFilter;
        });
    }
    
    // Update the timeline
    timeline.setItems(filteredItems);
    timeline.setGroups(filteredGroups);
    
    // Redraw the timeline
    timeline.redraw();
    
    // Add player labels if enabled
    if (document.getElementById('showPlayerLabels').checked) {
        addPlayerLabels(playerPositions, document.getElementById('visualization'));
    }
}

// Add player labels to the timeline
function addPlayerLabels(playerPositions, container) {
    // Remove any existing labels first
    removePlayerLabels();
    
    // Get the timeline canvas
    const canvas = container.querySelector('.vis-panel.vis-left');
    if (!canvas) return;
    
    // Add a label for each player
    Object.values(playerPositions).forEach(player => {
        const label = document.createElement('div');
        label.className = 'player-label';
        label.textContent = `${player.name} (${player.rating})`;
        label.style.position = 'absolute';
        label.style.left = '10px';
        label.style.top = `${40 + player.index * 50}px`; // Adjust based on your item height
        label.style.zIndex = '1000';
        label.style.pointerEvents = 'none';
        label.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
        label.style.padding = '2px 5px';
        label.style.borderRadius = '3px';
        label.style.fontSize = '12px';
        label.style.whiteSpace = 'nowrap';
        label.style.overflow = 'hidden';
        label.style.textOverflow = 'ellipsis';
        label.style.maxWidth = '200px';
        
        // Add dark mode support
        if (document.documentElement.getAttribute('data-bs-theme') === 'dark') {
            label.style.backgroundColor = 'rgba(43, 48, 53, 0.8)';
            label.style.color = '#f8f9fa';
        }
        
        container.appendChild(label);
    });
}

// Remove player labels from the timeline
function removePlayerLabels() {
    const labels = document.querySelectorAll('.player-label');
    labels.forEach(label => label.remove());
}

// Export functions for global access
window.initGraphicalView = initGraphicalView;
window.updateViewMode = updateViewMode;
window.applyFilters = applyFilters;
