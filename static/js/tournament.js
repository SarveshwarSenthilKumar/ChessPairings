// Tournament management functionality
function initMassDelete() {
    console.log('Initializing mass delete functionality');
    
    // Initialize elements
    const toggleMassDeleteBtn = document.getElementById('toggleMassDelete');
    const cancelMassDeleteBtn = document.getElementById('cancelMassDelete');
    const deleteSelectedBtn = document.getElementById('deleteSelected');
    const confirmDeleteBtn = document.getElementById('confirmDelete');
    
    if (!toggleMassDeleteBtn) {
        console.error('Mass delete toggle button not found!');
        return;
    }
    
    // Get the modal element
    const deleteModalEl = document.getElementById('deleteConfirmationModal');
    const deleteConfirmationModal = deleteModalEl ? new bootstrap.Modal(deleteModalEl) : null;
    
    if (!deleteConfirmationModal) {
        console.error('Delete confirmation modal not found!');
    }
    
    let selectedTournaments = new Set();
    
    // Toggle mass delete mode
    function toggleMassDeleteMode() {
        console.log('toggleMassDeleteMode called');
        const isMassDeleteMode = document.body.classList.toggle('mass-delete-mode');
        const checkboxes = document.querySelectorAll('.tournament-checkbox');
        console.log(`Found ${checkboxes.length} checkboxes`);
        
        // Toggle checkboxes visibility
        checkboxes.forEach(checkbox => {
            checkbox.style.display = isMassDeleteMode ? 'block' : 'none';
            if (!isMassDeleteMode) {
                checkbox.checked = false;
            }
        });
        
        // Toggle mass delete actions
        const massDeleteActions = document.querySelector('.mass-delete-actions');
        if (massDeleteActions) {
            massDeleteActions.style.display = isMassDeleteMode ? 'flex' : 'none';
        }
        
        // Reset selection when exiting mass delete mode
        if (!isMassDeleteMode) {
            selectedTournaments.clear();
            updateDeleteButton();
            
            // Remove selected class from all cards
            document.querySelectorAll('.tournament-card').forEach(card => {
                card.classList.remove('selected');
            });
        }
    }
    
    // Update delete button text with count
    function updateDeleteButton() {
        const count = selectedTournaments.size;
        if (deleteSelectedBtn) {
            deleteSelectedBtn.textContent = `Delete Selected (${count})`;
            deleteSelectedBtn.disabled = count === 0;
        }
        const deleteCount = document.getElementById('deleteCount');
        if (deleteCount) {
            deleteCount.textContent = count;
        }
    }
    
    // Handle checkbox changes
    document.addEventListener('change', function(e) {
        if (e.target && e.target.classList.contains('tournament-checkbox')) {
            const tournamentId = e.target.value;
            if (e.target.checked) {
                selectedTournaments.add(tournamentId);
                const card = e.target.closest('.tournament-card');
                if (card) card.classList.add('selected');
            } else {
                selectedTournaments.delete(tournamentId);
                const card = e.target.closest('.tournament-card');
                if (card) card.classList.remove('selected');
            }
            updateDeleteButton();
        }
    });
    
    // Toggle mass delete mode
    if (toggleMassDeleteBtn) {
        console.log('Adding click event listener to toggleMassDeleteBtn');
        toggleMassDeleteBtn.addEventListener('click', function(e) {
            console.log('Mass delete button clicked', e);
            e.preventDefault();
            e.stopPropagation();
            toggleMassDeleteMode();
        });
    } else {
        console.error('toggleMassDeleteBtn not found!');
    }
    
    // Cancel mass delete mode
    if (cancelMassDeleteBtn) {
        cancelMassDeleteBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            toggleMassDeleteMode();
        });
    }
    
    // Show delete confirmation
    if (deleteSelectedBtn) {
        deleteSelectedBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (selectedTournaments.size > 0) {
                console.log('Showing delete confirmation for', selectedTournaments.size, 'tournaments');
                if (deleteConfirmationModal) {
                    deleteConfirmationModal.show();
                } else {
                    console.error('Delete confirmation modal not found!');
                }
            } else {
                console.warn('No tournaments selected for deletion');
                showErrorToast('Please select at least one tournament to delete');
            }
        });
    }
    
    // Show success toast
    function showSuccessToast(message) {
        const toastEl = document.getElementById('deleteSuccessToast');
        if (toastEl) {
            const toastMessage = toastEl.querySelector('.toast-message');
            if (toastMessage) {
                toastMessage.textContent = message;
            }
            const toast = new bootstrap.Toast(toastEl);
            toast.show();
        }
    }
    
    // Show error toast
    function showErrorToast(message) {
        const toastEl = document.getElementById('errorToast');
        if (toastEl) {
            const toastMessage = toastEl.querySelector('.toast-message');
            if (toastMessage) {
                toastMessage.textContent = message;
            }
            const toast = new bootstrap.Toast(toastEl);
            toast.show();
        } else {
            console.error('Error toast element not found');
            alert('Error: ' + message);
        }
    }
    
    // Handle delete confirmation
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (!deleteConfirmationModal) {
                console.error('Delete confirmation modal not available');
                return;
            }
            const tournamentIds = Array.from(selectedTournaments);
            console.log('Deleting tournaments:', tournamentIds);
            
            if (tournamentIds.length === 0) {
                console.warn('No tournament IDs to delete');
                showErrorToast('No tournaments selected for deletion');
                return;
            }
            
            // Show loading state
            const originalText = confirmDeleteBtn.innerHTML;
            confirmDeleteBtn.disabled = true;
            confirmDeleteBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Deleting...';
            
            // Store the original button text for later restoration
            
            // Get CSRF token
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
            if (!csrfToken) {
                console.error('CSRF token not found');
                showErrorToast('Security error. Please refresh the page and try again.');
                return;
            }
            // Send delete request
            fetch('/tournament/mass_delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ tournament_ids: tournamentIds }),
                credentials: 'same-origin'
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.message || 'Failed to delete tournaments');
                    });
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Hide the modal
                    if (deleteConfirmationModal) {
                        deleteConfirmationModal.hide();
                    }
                    
                    // Remove deleted tournaments from the DOM
                    tournamentIds.forEach(id => {
                        const card = document.querySelector(`.tournament-card input[value="${id}"]`)?.closest('.tournament-card');
                        if (card) {
                            card.style.opacity = '0.5';
                            card.style.transition = 'opacity 0.3s ease';
                            setTimeout(() => card.remove(), 300);
                        }
                    });
                    
                    // Show success message
                    showSuccessToast(data.message || 'Tournament(s) deleted successfully');
                    
                    // Reset mass delete mode
                    toggleMassDeleteMode();
                    
                    // If no tournaments left, show empty state
                    const tournamentContainer = document.querySelector('.tournament-container');
                    if (tournamentContainer && !tournamentContainer.querySelector('.tournament-card')) {
                        window.location.reload(); // Reload to show empty state
                    }
                } else {
                    throw new Error(data.message || 'Failed to delete tournaments');
                }
            })
            .catch(error => {
                console.error('Error deleting tournaments:', error);
                showErrorToast(error.message || 'An error occurred while deleting tournaments');
            })
            .finally(() => {
                // Reset button state
                if (confirmDeleteBtn) {
                    confirmDeleteBtn.disabled = false;
                    confirmDeleteBtn.innerHTML = '<i class="fas fa-trash-alt me-1"></i> Delete Permanently';
                }
                
                // Hide the modal
                if (deleteConfirmationModal) {
                    deleteConfirmationModal.hide();
                }
                
                // Clear selection
                selectedTournaments.clear();
                updateDeleteButton();
                
                // Restore original button text
                if (originalText) {
                    confirmDeleteBtn.innerHTML = originalText;
                }
            });
        });
    }
    
    // Close modal on escape key
    // Handle escape key to exit mass delete mode
    document.addEventListener('keydown', function handleEscapeKey(e) {
        if (e.key === 'Escape' && document.body.classList.contains('mass-delete-mode')) {
            toggleMassDeleteMode();
        }
    });
}
