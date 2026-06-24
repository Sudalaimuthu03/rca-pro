(function () {
  "use strict";

  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function showError(input, errorEl, message) {
    input.classList.add("invalid");
    input.classList.remove("valid");
    errorEl.textContent = message;
    errorEl.classList.add("show");
  }

  function clearError(input, errorEl) {
    input.classList.remove("invalid");
    input.classList.add("valid");
    errorEl.classList.remove("show");
    errorEl.textContent = "";
  }

  function resetField(input, errorEl) {
    input.classList.remove("invalid", "valid");
    errorEl.classList.remove("show");
  }

  function validateEmail(input, errorEl) {
    const v = input.value.trim();
    if (!v) { showError(input, errorEl, "Email is required"); return false; }
    if (!EMAIL_RE.test(v)) { showError(input, errorEl, "Enter a valid email address"); return false; }
    clearError(input, errorEl);
    return true;
  }

  function validatePassword(input, errorEl, { checkStrength } = { checkStrength: false }) {
    const v = input.value;
    if (!v) { showError(input, errorEl, "Password is required"); return false; }
    if (checkStrength) {
      if (v.length < 8) { showError(input, errorEl, "Must be at least 8 characters"); return false; }
      if (!/[A-Za-z]/.test(v) || !/[0-9]/.test(v)) {
        showError(input, errorEl, "Must contain a letter and a number");
        return false;
      }
    }
    clearError(input, errorEl);
    return true;
  }

  function setLoading(btn, label, loading, loadingText, normalText) {
    btn.disabled = loading;
    label.innerHTML = loading
      ? `<span class="spinner"></span> ${loadingText}`
      : normalText;
  }

  function showBanner(banner, message) {
    banner.textContent = message;
    banner.classList.add("show");
  }

  function hideBanner(banner) {
    banner.classList.remove("show");
  }

  // ── Login ────────────────────────────────────────────────────────────────
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    const email = document.getElementById("email");
    const password = document.getElementById("password");
    const emailError = document.getElementById("emailError");
    const passwordError = document.getElementById("passwordError");
    const banner = document.getElementById("formBanner");
    const btn = document.getElementById("submitBtn");
    const label = document.getElementById("submitLabel");

    email.addEventListener("blur", () => validateEmail(email, emailError));
    email.addEventListener("input", () => resetField(email, emailError));
    password.addEventListener("input", () => resetField(password, passwordError));

    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideBanner(banner);
      const okEmail = validateEmail(email, emailError);
      const okPassword = validatePassword(password, passwordError);
      if (!okEmail || !okPassword) return;

      setLoading(btn, label, true, "Logging in…", "Log in");
      try {
        const res = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: email.value.trim(),
            password: password.value,
            remember: document.getElementById("remember").checked,
          }),
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
          showBanner(banner, data.error || "Invalid email or password");
          setLoading(btn, label, false, "", "Log in");
          return;
        }
        window.location.href = "/";
      } catch (err) {
        showBanner(banner, "Network error — please try again");
        setLoading(btn, label, false, "", "Log in");
      }
    });
  }

  // ── Signup ───────────────────────────────────────────────────────────────
  const signupForm = document.getElementById("signupForm");
  if (signupForm) {
    const name = document.getElementById("name");
    const email = document.getElementById("email");
    const password = document.getElementById("password");
    const confirmPassword = document.getElementById("confirmPassword");
    const nameError = document.getElementById("nameError");
    const emailError = document.getElementById("emailError");
    const passwordError = document.getElementById("passwordError");
    const confirmPasswordError = document.getElementById("confirmPasswordError");
    const banner = document.getElementById("formBanner");
    const btn = document.getElementById("submitBtn");
    const label = document.getElementById("submitLabel");

    function validateName() {
      const v = name.value.trim();
      if (v.length < 2) { showError(name, nameError, "Name must be at least 2 characters"); return false; }
      clearError(name, nameError);
      return true;
    }

    function validateConfirm() {
      if (confirmPassword.value !== password.value) {
        showError(confirmPassword, confirmPasswordError, "Passwords do not match");
        return false;
      }
      clearError(confirmPassword, confirmPasswordError);
      return true;
    }

    name.addEventListener("blur", validateName);
    name.addEventListener("input", () => resetField(name, nameError));
    email.addEventListener("blur", () => validateEmail(email, emailError));
    email.addEventListener("input", () => resetField(email, emailError));
    password.addEventListener("blur", () => validatePassword(password, passwordError, { checkStrength: true }));
    password.addEventListener("input", () => resetField(password, passwordError));
    confirmPassword.addEventListener("blur", validateConfirm);
    confirmPassword.addEventListener("input", () => resetField(confirmPassword, confirmPasswordError));

    signupForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideBanner(banner);
      const okName = validateName();
      const okEmail = validateEmail(email, emailError);
      const okPassword = validatePassword(password, passwordError, { checkStrength: true });
      const okConfirm = validateConfirm();
      if (!okName || !okEmail || !okPassword || !okConfirm) return;

      setLoading(btn, label, true, "Creating account…", "Create account");
      try {
        const res = await fetch("/api/auth/signup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: name.value.trim(),
            email: email.value.trim(),
            password: password.value,
            confirm_password: confirmPassword.value,
          }),
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
          const firstError = data.errors
            ? Object.values(data.errors)[0][0]
            : data.error || "Something went wrong";
          showBanner(banner, firstError);
          setLoading(btn, label, false, "", "Create account");
          return;
        }
        window.location.href = "/";
      } catch (err) {
        showBanner(banner, "Network error — please try again");
        setLoading(btn, label, false, "", "Create account");
      }
    });
  }
})();
