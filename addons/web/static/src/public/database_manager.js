document.addEventListener("DOMContentLoaded", function () {
    const onboarding = document.querySelector(".o_database_onboarding");
    const manager = document.querySelector("body.o_carbon_database_manager > .container");
    const onboardingForm = document.querySelector(".o_database_onboarding_form");
    const finalStep = 5;
    let onboardingStep = 1;

    // The QWeb manager keeps all dialogs inside its container. Move the
    // onboarding workspace to the page root so hiding the manager does not
    // hide the new flow with it.
    if (onboarding) {
        document.body.appendChild(onboarding);
    }

    function showOnboardingStep(step) {
        if (step === 4) {
            syncSopSections();
        }
        onboardingStep = step;
        onboarding.querySelectorAll(".o_onboarding_step").forEach((element) => {
            element.classList.toggle("is-active", Number(element.dataset.step) === step);
        });
        onboarding.querySelectorAll("[data-step-indicator]").forEach((element) => {
            const indicatorStep = Number(element.dataset.stepIndicator);
            element.classList.toggle("is-active", indicatorStep === step);
            element.classList.toggle("is-complete", indicatorStep < step);
        });
        onboarding.querySelector(".o_onboarding_back").hidden = step === 1;
        onboarding.querySelector(".o_onboarding_next").hidden = step === finalStep;
        onboarding.querySelector(".o_onboarding_submit").hidden = step !== finalStep;
        onboarding.querySelector(".o_onboarding_content").scrollTop = 0;
    }

    function syncSopDependencies(section) {
        section.querySelectorAll("[data-enabled-by]").forEach((control) => {
            const controller = onboardingForm.elements[control.dataset.enabledBy];
            const isEnabled = Boolean(controller?.checked);
            control.hidden = !isEnabled;
            control.querySelectorAll("input, select").forEach((field) => {
                field.disabled = !isEnabled;
            });
        });
    }

    function syncSopSections() {
        const sections = [...onboarding.querySelectorAll("[data-sop-app]")];
        let visibleCount = 0;
        sections.forEach((section) => {
            const appOption = onboardingForm.elements[section.dataset.sopApp];
            const isSelected = Boolean(appOption?.checked);
            section.hidden = !isSelected;
            section.querySelectorAll("input, select").forEach((field) => {
                field.disabled = !isSelected;
            });
            if (isSelected) {
                visibleCount += 1;
                syncSopDependencies(section);
            }
        });
        onboarding.querySelector(".o_sop_empty").hidden = visibleCount !== 0;
    }

    function syncCompanyLocalization(useCountryDefault = false) {
        const country = onboardingForm.elements.country_code;
        const currency = onboardingForm.elements.currency_code;
        const selectedCountry = country.selectedOptions[0];
        if ((useCountryDefault || !currency.value) && selectedCountry?.dataset.currency) {
            currency.value = selectedCountry.dataset.currency;
        }
        const currencyCode = currency.value || "Currency";
        onboarding.querySelectorAll("[data-currency-code]").forEach((element) => {
            element.textContent = currencyCode;
        });
        const countryName = country.value ? selectedCountry.text : "company country";
        onboarding.querySelectorAll("[data-tax-template]").forEach((element) => {
            element.textContent = `Automatic ${countryName} fiscal localization`;
        });
    }

    function updateReview() {
        const selectedApps = [...onboarding.querySelectorAll(".o_onboarding_apps input[name^='install_']:checked")]
            .map((input) => input.closest("label").querySelector("strong").textContent);
        const reviewValues = {
            name: onboardingForm.elements.name.value,
            company_name: onboardingForm.elements.company_name.value,
            address: [onboardingForm.elements.street.value, onboardingForm.elements.city.value, onboardingForm.elements.zip.value].filter(Boolean).join(", ") || "Not provided",
            vat: onboardingForm.elements.vat.value || "Not provided",
            login: onboardingForm.elements.login.value,
            lang: onboardingForm.elements.lang.selectedOptions[0].text,
            country_code: onboardingForm.elements.country_code.selectedOptions[0].text,
            currency_code: onboardingForm.elements.currency_code.selectedOptions[0].text,
            modules: selectedApps.join(", ") || "Core only",
            demo: onboardingForm.elements.demo.checked ? "Included" : "Not included",
        };
        Object.entries(reviewValues).forEach(([name, value]) => {
            onboarding.querySelector(`[data-review="${name}"]`).textContent = value;
        });

        const operations = onboarding.querySelector('[data-review="operations"]');
        operations.replaceChildren();
        const selectedSections = [...onboarding.querySelectorAll("[data-sop-app]:not([hidden])")];
        if (!selectedSections.length) {
            operations.textContent = "Standard core settings";
            return;
        }
        selectedSections.forEach((section) => {
            const group = document.createElement("section");
            const heading = document.createElement("h4");
            const flow = document.createElement("p");
            const list = document.createElement("ul");
            heading.textContent = section.dataset.sopName;
            flow.textContent = `Suggested SOP: ${section.dataset.sopFlow}`;
            section.querySelectorAll(".o_sop_control:not([hidden])").forEach((control) => {
                const field = control.querySelector("input, select");
                const derivedValue = control.querySelector("[data-derived-value]");
                if ((!field && !derivedValue) || field?.disabled) {
                    return;
                }
                const item = document.createElement("li");
                let answer;
                if (derivedValue) {
                    answer = derivedValue.textContent;
                } else if (field.type === "checkbox") {
                    answer = field.checked ? "Yes" : "No";
                } else if (field.tagName === "SELECT") {
                    answer = field.selectedOptions[0].text;
                } else {
                    answer = field.value;
                    if (control.querySelector("[data-currency-code]")) {
                        answer = `${answer} ${onboardingForm.elements.currency_code.value}`;
                    }
                }
                item.textContent = `${control.dataset.sopLabel}: ${answer}`;
                list.appendChild(item);
            });
            group.append(heading, flow, list);
            operations.appendChild(group);
        });
    }

    function closeOnboarding() {
        onboarding.hidden = true;
        manager.hidden = false;
        document.body.classList.remove("o_onboarding_open");
    }

    document.querySelector(".o_database_create_start")?.addEventListener("click", () => {
        manager.hidden = true;
        onboarding.hidden = false;
        document.body.classList.add("o_onboarding_open");
        showOnboardingStep(1);
        onboarding.querySelector("input")?.focus();
    });
    document.querySelector(".o_database_error_retry")?.addEventListener("click", () => {
        document.querySelector(".o_database_create_start")?.click();
    });
    document.querySelector(".o_database_error_dismiss")?.addEventListener("click", (ev) => {
        ev.target.closest(".o_database_error")?.remove();
    });
    onboarding?.querySelector(".o_onboarding_close").addEventListener("click", closeOnboarding);
    onboarding?.querySelector(".o_onboarding_back").addEventListener("click", () => showOnboardingStep(onboardingStep - 1));
    onboarding?.querySelectorAll(".o_onboarding_apps input[name^='install_']").forEach((input) => {
        input.addEventListener("change", syncSopSections);
    });
    onboarding?.querySelectorAll(".o_sop_control input[type='checkbox']").forEach((input) => {
        input.addEventListener("change", () => syncSopDependencies(input.closest(".o_sop_section")));
    });
    onboardingForm?.elements.country_code.addEventListener("change", () => {
        syncCompanyLocalization(true);
    });
    onboardingForm?.elements.currency_code.addEventListener("change", () => {
        syncCompanyLocalization();
    });
    syncCompanyLocalization();
    syncSopSections();
    onboarding?.querySelector(".o_onboarding_next").addEventListener("click", () => {
        const currentStep = onboarding.querySelector(`.o_onboarding_step[data-step="${onboardingStep}"]`);
        const invalidField = [...currentStep.querySelectorAll("input, select")].find((field) => !field.checkValidity());
        if (invalidField) {
            invalidField.reportValidity();
            return;
        }
        if (onboardingStep === 4) {
            updateReview();
        }
        showOnboardingStep(onboardingStep + 1);
    });
    onboarding?.querySelectorAll(".o_logo_upload input[type='file']").forEach((input) => {
        input.addEventListener("change", () => {
            const preview = input.closest(".o_logo_upload").querySelector(".o_logo_preview");
            preview.replaceChildren();
            if (!input.files?.[0]) {
                preview.innerHTML = '<i class="fa fa-image" aria-hidden="true"></i>';
                return;
            }
            const image = document.createElement("img");
            image.alt = "Logo preview";
            image.src = URL.createObjectURL(input.files[0]);
            image.addEventListener("load", () => URL.revokeObjectURL(image.src), { once: true });
            preview.appendChild(image);
        });
    });
    onboardingForm?.addEventListener("submit", (ev) => {
        if (!onboardingForm.checkValidity()) {
            return;
        }
        const submitButton = onboarding.querySelector(".o_onboarding_submit");
        if (submitButton.disabled) {
            ev.preventDefault();
            return;
        }
        submitButton.disabled = true;
        const token = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        onboardingForm.querySelector(".o_setup_token").value = token;
        onboardingForm.setAttribute("aria-busy", "true");
        onboarding.querySelector(".o_database_creation_progress").hidden = false;
        const progressInner = onboarding.querySelector(".o_creation_progress_inner");
        const progressTrack = onboarding.querySelector(".o_creation_progress_track");
        const progressBar = progressTrack.querySelector("span");
        const progressStatus = onboarding.querySelector(".o_creation_status");
        const progressDetail = onboarding.querySelector(".o_creation_detail");
        const progressPercent = onboarding.querySelector(".o_creation_percent");
        const progressLog = onboarding.querySelector(".o_creation_log");
        const progressLogCount = onboarding.querySelector(".o_creation_log_count");
        const stages = ["database", "carbon", "company", "applications", "signin"];
        const statusLabels = {
            waiting: "Starting database setup...",
            validating: "Validating database settings...",
            database: "Creating the database and core records...",
            carbon: "Initializing the Carbon interface...",
            company: "Applying company and regional settings...",
            applications: "Installing your selected applications...",
            signin: "Preparing your administrator session...",
            complete: "Workspace ready. Opening NWOS...",
            error: "Setup needs attention. Returning to recovery options...",
        };
        const renderedLogIds = new Set();
        const creationStartedAt = Date.now();
        const updateElapsedTime = () => {
            const elapsedSeconds = Math.floor((Date.now() - creationStartedAt) / 1000);
            const minutes = String(Math.floor(elapsedSeconds / 60)).padStart(2, "0");
            const seconds = String(elapsedSeconds % 60).padStart(2, "0");
            onboarding.querySelector(".o_creation_elapsed").textContent = `${minutes}:${seconds} elapsed`;
        };
        const elapsedTimer = window.setInterval(updateElapsedTime, 1000);

        const appendProgressEvent = (event) => {
            if (renderedLogIds.has(event.id)) {
                return;
            }
            renderedLogIds.add(event.id);
            progressLog.querySelector(".o_creation_log_empty")?.remove();
            const logEntry = document.createElement("div");
            const timestamp = document.createElement("time");
            const marker = document.createElement("span");
            const content = document.createElement("span");
            const title = document.createElement("strong");
            logEntry.className = `is-${event.level || "info"}`;
            timestamp.textContent = new Date(event.timestamp || Date.now()).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
            });
            marker.className = "o_creation_log_marker";
            title.textContent = event.message || statusLabels[event.stage] || statusLabels.waiting;
            content.appendChild(title);
            if (event.detail) {
                const detail = document.createElement("small");
                detail.textContent = event.detail;
                content.appendChild(detail);
            }
            logEntry.append(timestamp, marker, content);
            progressLog.appendChild(logEntry);
            progressLog.scrollTop = progressLog.scrollHeight;
            progressLogCount.textContent = `${renderedLogIds.size} event${renderedLogIds.size === 1 ? "" : "s"}`;
        };

        let pollProgress;
        const refreshProgress = async () => {
            try {
                const response = await fetch(`/web/database/create/progress/${encodeURIComponent(token)}`, { cache: "no-store" });
                if (!response.ok) {
                    throw new Error(`Progress request failed with ${response.status}`);
                }
                const progress = await response.json();
                const percent = Math.max(0, Math.min(100, Number(progress.percent ?? 2)));
                const creationState = progress.stage === "error"
                    ? "error"
                    : progress.stage === "complete" ? "complete" : "running";
                progressInner.dataset.creationState = creationState;
                progressStatus.textContent = progress.message || statusLabels[progress.stage] || statusLabels.waiting;
                progressDetail.textContent = progress.detail || "The server is continuing with your workspace setup.";
                progressPercent.textContent = `${percent}%`;
                progressBar.style.width = `${percent}%`;
                progressTrack.setAttribute("aria-valuenow", String(percent));
                (progress.logs || []).forEach(appendProgressEvent);
                const currentIndex = ["waiting", "validating"].includes(progress.stage)
                    ? 0
                    : stages.indexOf(progress.stage);
                onboarding.querySelectorAll("[data-progress-stage]").forEach((item) => {
                    const itemIndex = stages.indexOf(item.dataset.progressStage);
                    item.classList.toggle("is-active", itemIndex === currentIndex);
                    item.classList.toggle("is-complete", currentIndex > itemIndex || progress.stage === "complete");
                });
                if (progress.stage === "complete" || progress.stage === "error") {
                    window.clearInterval(pollProgress);
                    window.clearInterval(elapsedTimer);
                    updateElapsedTime();
                }
            } catch {
                progressInner.dataset.creationState = "reconnecting";
                progressDetail.textContent = "Progress connection interrupted. Retrying automatically...";
            }
        };
        refreshProgress();
        pollProgress = window.setInterval(refreshProgress, 600);
    });

    // Password visibility controls use direct bindings so browser credential
    // overlays cannot interfere with delegated event targeting.
    document.querySelectorAll(".o_little_eye").forEach((eyeToggle) => {
        eyeToggle.addEventListener("click", (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            const formControl = eyeToggle.closest(".input-group")?.querySelector(".form-control");
            if (!formControl) {
                return;
            }
            const showPassword = formControl.type === "password";
            formControl.type = showPassword ? "text" : "password";
            eyeToggle.setAttribute("aria-label", showPassword ? "Hide password" : "Show password");
            eyeToggle.setAttribute("aria-pressed", String(showPassword));
            const icon = eyeToggle.querySelector(".fa") || eyeToggle;
            icon.classList.toggle("fa-eye", !showPassword);
            icon.classList.toggle("fa-eye-slash", showPassword);
        });
    });

    // db modal
    document.body.addEventListener("click", function (ev) {
        if (ev.target.classList.contains("o_database_action")) {
            ev.preventDefault();
            const db = ev.target.getAttribute("data-db");
            const target = ev.target.getAttribute("data-bs-target");
            const modal = Modal.getOrCreateInstance(document.querySelector(target));
            const inputName = modal._element.querySelector("input[name=name]");
            if (inputName) {
                inputName.value = db;
            }
            modal.show();
        }
    });

   document.getElementById('backup_format').addEventListener("change", function (ev) {
            ev.preventDefault();
            const no_filestore_flag = document.getElementById("filestore_div");
            if (no_filestore_flag) {
                if (ev.target.value != "zip") {
                    no_filestore_flag.classList.add("d-none");
                } else {
                    no_filestore_flag.classList.remove("d-none");
                }
            }
    });

    // close modal on submit
    const modals = document.querySelectorAll(".modal");
    for (const modalEl of modals) {
        modalEl.addEventListener("submit", function (ev) {
            const form = ev.target.closest("form");
            if (form && !form.checkValidity?.()) {
                return;
            }
            const modal = Modal.getOrCreateInstance(modalEl);
            modal.hide();
            if (modalEl.classList.contains("o_database_backup")) {
                if (!document.querySelector(".alert-backup-long")) {
                    const listGroup = document.querySelector(".list-group");
                    if (listGroup) {
                        const alert = document.createElement("div");
                        alert.className = "alert alert-info alert-backup-long";
                        alert.textContent =
                            "The backup is on its way; if your database has a lot of data, you may want to go grab a coffee...";
                        listGroup.parentNode.insertBefore(alert, listGroup);
                    }
                }
            }
        });
    }
    // generate a random master password
    // removed l1O0 to avoid confusions
    const charset = "abcdefghijkmnpqrstuvwxyz23456789";
    let password = "";
    for (let i = 0; i < 12; ++i) {
        password += charset.charAt(Math.floor(Math.random() * charset.length));
        if (i === 3 || i === 7) {
            password += "-";
        }
    }
    const masterPwds = document.getElementsByClassName("generated_master_pwd");
    for (const pwdElement of masterPwds) {
        pwdElement.innerText = password;
    }
    const masterPwdInputs = document.querySelectorAll(".generated_master_pwd_input");
    for (const pwdInput of masterPwdInputs) {
        pwdInput.value = password;
        pwdInput.setAttribute("autocomplete", "new-password");
    }
});
