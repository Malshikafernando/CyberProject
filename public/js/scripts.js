document.addEventListener('DOMContentLoaded', function () {
    const demoFillButton = document.getElementById('demo-fill');
    if (demoFillButton) {
        demoFillButton.addEventListener('click', function () {
            const defaultValues = {
                firewall_status: 'Yes',
                mfa_usage: 'Yes',
                encryption_usage: 'Yes',
                employee_training_score: 75,
                phishing_test_score: 70,
                unpatched_vulnerabilities: 1,
                incident_history_count: 0,
                password_policy_strength: 8,
                backup_frequency_days: 7,
                network_monitoring_level: 8,
            };
            Object.keys(defaultValues).forEach(function (key) {
                const element = document.querySelector(`[name='${key}']`);
                if (element) {
                    element.value = defaultValues[key];
                }
            });
        });
    }

    const revealNodes = document.querySelectorAll('.reveal');
    if ('IntersectionObserver' in window && revealNodes.length > 0) {
        const observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.style.animationDelay = '0.08s';
                    entry.target.classList.add('revealed');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15 });

        revealNodes.forEach(function (node) {
            observer.observe(node);
        });
    }
     <script>
        document.getElementById('download-btn').addEventListener('click', function() {
            // Select the element to convert
            const element = document.getElementById('content');
            
            // Configuration options
            const options = {
                margin:       1,
                filename:     'document.pdf',
                image:        { type: 'jpeg', quality: 0.98 },
                html2canvas:  { scale: 2 },
                jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
            };

            // Run the converter
            html2pdf().set(options).from(element).save();
        });
    </script>
});
