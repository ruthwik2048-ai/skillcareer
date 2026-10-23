(() => {
  const eyeIcon = `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"></path>
      <circle cx="12" cy="12" r="3"></circle>
    </svg>`;
  const eyeOffIcon = `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8"></path>
      <path d="M9.9 5.2A10.8 10.8 0 0 1 12 5c6.4 0 10 7 10 7a16 16 0 0 1-3.1 3.8M6.2 6.2C3.5 8.1 2 12 2 12s3.6 7 10 7c1 0 1.9-.2 2.8-.5"></path>
    </svg>`;

  function addPasswordToggles() {
    if (!document.body.classList.contains("login")) {
      return;
    }

    document.querySelectorAll('input[type="password"]:not([data-visibility-toggle])')
      .forEach((input) => {
        input.dataset.visibilityToggle = "true";

        const button = document.createElement("button");
        button.type = "button";
        button.className = "sc-password-toggle";
        button.setAttribute("aria-label", "Show password");
        button.setAttribute("aria-pressed", "false");
        button.title = "Show password";
        button.innerHTML = eyeIcon;

        button.addEventListener("click", () => {
          const showPassword = input.type === "password";
          input.type = showPassword ? "text" : "password";
          button.setAttribute("aria-label", showPassword ? "Hide password" : "Show password");
          button.setAttribute("aria-pressed", String(showPassword));
          button.title = showPassword ? "Hide password" : "Show password";
          button.innerHTML = showPassword ? eyeOffIcon : eyeIcon;
          input.focus();
        });

        input.insertAdjacentElement("afterend", button);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", addPasswordToggles, { once: true });
  } else {
    addPasswordToggles();
  }
})();
