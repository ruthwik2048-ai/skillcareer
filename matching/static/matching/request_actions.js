document.addEventListener("DOMContentLoaded", () => {
    const actionSelect = document.querySelector(
        "#changelist-form .actions select[name='action']",
    );
    const actionButton = document.querySelector(
        "#changelist-form .actions button[name='index']",
    );

    if (!actionSelect || !actionButton) {
        return;
    }

    const updateActionButton = () => {
        if (actionSelect.value === "approve_requests") {
            actionButton.textContent = "Accept";
        } else if (actionSelect.value === "reject_requests") {
            actionButton.textContent = "Reject";
        } else {
            actionButton.textContent = "Apply";
        }
    };

    actionSelect.addEventListener("change", updateActionButton);
    updateActionButton();
});
