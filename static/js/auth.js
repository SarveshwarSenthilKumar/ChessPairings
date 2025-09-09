// Password strength meter and form validation for auth pages
document.addEventListener('DOMContentLoaded', function() {
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirm_password');
    const passwordStrength = document.getElementById('passwordStrength');
    const passwordRequirements = document.querySelectorAll('.password-requirement');
    
    if (passwordInput && passwordStrength) {
        // Password strength requirements
        const requirements = [
            { regex: /.{8,}/, index: 0 }, // At least 8 characters
            { regex: /[A-Z]/, index: 1 }, // At least one uppercase letter
            { regex: /[a-z]/, index: 2 }, // At least one lowercase letter
            { regex: /[0-9]/, index: 3 }, // At least one number
            { regex: /[^A-Za-z0-9]/, index: 4 } // At least one special character
        ];

        // Check password requirements
        function checkPasswordRequirements(password) {
            requirements.forEach(requirement => {
                const isValid = requirement.regex.test(password);
                const requirementElement = passwordRequirements[requirement.index];
                
                if (requirementElement) {
                    const icon = requirementElement.querySelector('i');
                    requirementElement.classList.toggle('valid', isValid);
                    requirementElement.classList.toggle('invalid', !isValid);
                    
                    if (icon) {
                        icon.className = isValid ? 'fas fa-check-circle' : 'fas fa-times-circle';
                    }
                }
            });
        }

        // Update password strength indicator
        function updatePasswordStrength() {
            if (!passwordInput || !passwordStrength) return;
            
            const password = passwordInput.value;
            let strength = 0;
            
            // Check each requirement
            requirements.forEach(requirement => {
                if (requirement.regex.test(password)) {
                    strength++;
                }
            });
            
            // Update strength meter
            const strengthClasses = ['strength-0', 'strength-1', 'strength-2', 'strength-3', 'strength-4'];
            passwordStrength.className = '';
            passwordStrength.classList.add(strengthClasses[Math.min(strength, 4)]);
            
            // Check if all requirements are met
            const isStrong = strength >= 4; // Require at least 4 out of 5 requirements
            passwordInput.setCustomValidity(isStrong ? '' : 'Password does not meet requirements');
            
            return isStrong;
        }

        // Validate password match
        function validatePasswordMatch() {
            if (!confirmPasswordInput) return true;
            
            const password = passwordInput.value;
            const confirmPassword = confirmPasswordInput.value;
            const isMatching = password === confirmPassword;
            
            confirmPasswordInput.setCustomValidity(isMatching ? '' : 'Passwords do not match');
            return isMatching;
        }

        // Event listeners
        passwordInput.addEventListener('input', function() {
            checkPasswordRequirements(this.value);
            updatePasswordStrength();
            
            if (confirmPasswordInput && confirmPasswordInput.value) {
                validatePasswordMatch();
            }
        });
        
        if (confirmPasswordInput) {
            confirmPasswordInput.addEventListener('input', validatePasswordMatch);
        }
        
        // Initial check
        if (passwordInput.value) {
            checkPasswordRequirements(passwordInput.value);
            updatePasswordStrength();
        }
    }
    
    // Form submission handler
    const authForm = document.querySelector('.auth-form');
    if (authForm) {
        authForm.addEventListener('submit', function(event) {
            if (passwordInput && !updatePasswordStrength()) {
                event.preventDefault();
                return false;
            }
            
            if (confirmPasswordInput && !validatePasswordMatch()) {
                event.preventDefault();
                return false;
            }
            
            return true;
        });
    }
});
