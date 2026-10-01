document.addEventListener("DOMContentLoaded", function () {
    const menuButton = document.querySelector(".menu-toggle");
    const navigation = document.querySelector(".site-nav");

    if (menuButton && navigation) {
        menuButton.addEventListener("click", function () {
            const open = navigation.classList.toggle("open");
            menuButton.setAttribute("aria-expanded", String(open));
            document.body.classList.toggle("menu-open", open);
        });
        navigation.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", function () {
                navigation.classList.remove("open");
                menuButton.setAttribute("aria-expanded", "false");
                document.body.classList.remove("menu-open");
            });
        });
    }

    const form = document.getElementById("assessment-form");
    if (!form) return;

    const steps = Array.from(form.querySelectorAll(".form-step"));
    const indicators = Array.from(document.querySelectorAll("[data-step-indicator]"));
    const previousButton = document.getElementById("previous-step");
    const nextButton = document.getElementById("next-step");
    const predictButton = document.getElementById("predict-button");
    const progressFill = document.getElementById("progress-fill");
    const currentStepNumber = document.getElementById("current-step-number");
    const stepStatus = document.getElementById("step-status");
    const reviewSummary = document.getElementById("review-summary");
    const analysisOverlay = document.getElementById("analysis-overlay");
    const config = window.assessmentConfig || { roleDepartmentMap: {}, stepTitles: [] };
    let currentStep = 0;
    let dirty = false;
    let submitting = false;

    function fieldLabel(input) {
        const wrapper = input.closest("[data-field-wrapper]");
        const label = wrapper && wrapper.querySelector(".field-label-row label");
        return label ? label.textContent.replace("*", "").trim() : input.name;
    }

    function clearFieldError(input) {
        const wrapper = input.closest("[data-field-wrapper]");
        if (!wrapper) return;
        wrapper.classList.remove("invalid");
        const error = wrapper.querySelector(".field-error");
        if (error) error.textContent = "";
    }

    function showFieldError(input, message) {
        const wrapper = input.closest("[data-field-wrapper]");
        if (!wrapper) return;
        wrapper.classList.add("invalid");
        const error = wrapper.querySelector(".field-error");
        if (error) error.textContent = message;
    }

    function validateStep(index) {
        const step = steps[index];
        if (!step || index === steps.length - 1) return true;
        const fields = Array.from(step.querySelectorAll("input[required], select[required]"));
        let firstInvalid = null;
        const checkedNames = new Set();

        fields.forEach(function (field) {
            if (field.type === "radio") {
                if (checkedNames.has(field.name)) return;
                checkedNames.add(field.name);
                const group = step.querySelectorAll(`input[name="${field.name}"]`);
                const selected = Array.from(group).some(function (item) { return item.checked; });
                if (!selected) {
                    showFieldError(field, `Select an option for ${fieldLabel(field)}.`);
                    firstInvalid = firstInvalid || field;
                } else {
                    clearFieldError(field);
                }
                return;
            }

            clearFieldError(field);
            if (!field.value.trim()) {
                showFieldError(field, `${fieldLabel(field)} is required.`);
                firstInvalid = firstInvalid || field;
                return;
            }
            if (field.type === "number") {
                const value = Number(field.value);
                const minimum = Number(field.min);
                const maximum = Number(field.max);
                if (!Number.isFinite(value) || value < minimum || value > maximum) {
                    showFieldError(field, `Enter a value between ${minimum} and ${maximum}.`);
                    firstInvalid = firstInvalid || field;
                }
            }
        });

        if (firstInvalid) {
            firstInvalid.focus();
            firstInvalid.closest("[data-field-wrapper]").scrollIntoView({ behavior: "smooth", block: "center" });
            return false;
        }
        return true;
    }

    function displayValue(field) {
        if (field.type === "radio") {
            const selected = form.querySelector(`input[name="${field.name}"]:checked`);
            return selected ? selected.nextElementSibling.textContent.trim() : "Not provided";
        }
        if (field.tagName === "SELECT") {
            return field.options[field.selectedIndex].text;
        }
        return field.value || "Not provided";
    }

    function buildReview() {
        reviewSummary.innerHTML = "";
        steps.slice(0, -1).forEach(function (step, index) {
            const group = document.createElement("section");
            group.className = "review-group";
            const header = document.createElement("div");
            header.className = "review-group-header";
            const heading = document.createElement("h3");
            heading.textContent = config.stepTitles[index] || `Step ${index + 1}`;
            const edit = document.createElement("button");
            edit.type = "button";
            edit.className = "review-edit";
            edit.textContent = "Edit";
            edit.addEventListener("click", function () { showStep(index); });
            header.append(heading, edit);

            const items = document.createElement("div");
            items.className = "review-items";
            const seen = new Set();
            step.querySelectorAll("input, select").forEach(function (field) {
                if (!field.name || field.name === "assessment_reference" || seen.has(field.name)) return;
                seen.add(field.name);
                const row = document.createElement("div");
                const label = document.createElement("span");
                label.textContent = fieldLabel(field);
                const value = document.createElement("strong");
                value.textContent = displayValue(field);
                row.append(label, value);
                items.appendChild(row);
            });
            group.append(header, items);
            reviewSummary.appendChild(group);
        });
    }

    function showStep(index, scrollToTop = true) {
        currentStep = Math.max(0, Math.min(index, steps.length - 1));
        steps.forEach(function (step, stepIndex) {
            const active = stepIndex === currentStep;
            step.classList.toggle("active", active);
            step.setAttribute("aria-hidden", String(!active));
        });
        indicators.forEach(function (indicator, indicatorIndex) {
            indicator.classList.toggle("active", indicatorIndex === currentStep);
            indicator.classList.toggle("completed", indicatorIndex < currentStep);
        });
        previousButton.hidden = currentStep === 0;
        nextButton.hidden = currentStep === steps.length - 1;
        predictButton.hidden = currentStep !== steps.length - 1;
        currentStepNumber.textContent = String(currentStep + 1);
        progressFill.style.width = `${((currentStep + 1) / steps.length) * 100}%`;
        stepStatus.textContent = config.stepTitles[currentStep] || "Assessment";
        if (currentStep === steps.length - 1) buildReview();
        if (scrollToTop) {
            const intro = document.querySelector(".assessment-intro");
            const headerOffset = 92;
            const targetTop = intro.getBoundingClientRect().top + window.scrollY - headerOffset;
            window.scrollTo({ top: targetTop, behavior: "smooth" });
        }
    }

    nextButton.addEventListener("click", function () {
        if (validateStep(currentStep)) showStep(currentStep + 1);
    });
    previousButton.addEventListener("click", function () { showStep(currentStep - 1); });

    const roleField = document.getElementById("employee_role");
    const departmentField = document.getElementById("department");
    const roleGuidanceTitle = document.getElementById("role-guidance-title");
    const roleGuidanceCopy = document.getElementById("role-guidance-copy");
    const roleGuidance = [
        [/finance|bank/i, "Financial data protection", "Focus on payment approvals, sensitive financial records, and account compromise controls."],
        [/administrator|cybersecurity|it support/i, "Privileged access protection", "Focus on administrative access, patching, monitoring, and infrastructure safeguards."],
        [/human|hr /i, "Employee data protection", "Focus on personal records, account access, policy compliance, and secure data handling."],
        [/operations/i, "Operational resilience", "Focus on service continuity, device security, access reviews, and incident readiness."],
        [/software/i, "Secure development practices", "Focus on source access, vulnerability management, authentication, and secure change controls."],
        [/sales|customer/i, "Customer data protection", "Focus on phishing resistance, mobile security, credential safety, and customer information."],
        [/lecturer|academic/i, "Academic information protection", "Focus on account security, research data, shared systems, and phishing resistance."],
        [/management|executive/i, "Executive risk protection", "Focus on high-value account access, sensitive decisions, impersonation, and incident readiness."]
    ];

    function updateRoleGuidance() {
        if (!roleField || !roleGuidanceTitle || !roleGuidanceCopy) return;
        const match = roleGuidance.find(function (item) { return item[0].test(roleField.value); });
        roleGuidanceTitle.textContent = match ? match[1] : "Role-aware assessment";
        roleGuidanceCopy.textContent = match ? match[2] : "The questions are interpreted using this employee's access and responsibilities.";
    }
    function synchronizeDepartment() {
        if (roleField && departmentField && config.roleDepartmentMap[roleField.value]) {
            departmentField.value = config.roleDepartmentMap[roleField.value];
        }
    }
    if (roleField) roleField.addEventListener("change", function () {
        synchronizeDepartment();
        updateRoleGuidance();
    });
    synchronizeDepartment();
    updateRoleGuidance();

    form.addEventListener("input", function (event) {
        dirty = true;
        if (event.target.matches("input, select")) clearFieldError(event.target);
    });
    form.addEventListener("change", function (event) {
        dirty = true;
        if (event.target.matches("input, select")) clearFieldError(event.target);
    });
    form.addEventListener("submit", function () {
        submitting = true;
        predictButton.classList.add("loading");
        predictButton.querySelector("span").textContent = "Analyzing assessment";
        if (analysisOverlay) {
            analysisOverlay.classList.add("visible");
            analysisOverlay.setAttribute("aria-hidden", "false");
        }
    });
    window.addEventListener("beforeunload", function (event) {
        if (!dirty || submitting) return;
        event.preventDefault();
        event.returnValue = "";
    });

    showStep(0, false);
});
