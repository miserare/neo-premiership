import { type FormEvent, useState } from "react";

import SaveStatus from "../components/SaveStatus";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { api, ApiError } from "../lib/api";

export default function AdminAccountPage() {
  useDocumentTitle("Admin Account");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function clearFields() {
    setCurrentPassword("");
    setNewPassword("");
    setConfirmPassword("");
  }

  async function handleChangePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setNotice(null);

    if (newPassword !== confirmPassword) {
      setError("The new passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    try {
      await api.admin.changePassword(currentPassword, newPassword);
      clearFields();
      // Rotating the password revokes every session including this one, so the
      // layout will drop back to the sign-in form on the next request.
      setNotice("Password changed. All sessions were signed out - please sign in again.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Your current password is incorrect.");
      } else if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Could not reach the server.");
      }
      setCurrentPassword("");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSignOutEverywhere() {
    if (!window.confirm("Sign out of every device, including this one?")) return;
    setError(null);
    try {
      await api.admin.logoutEverywhere();
      // A full reload, deliberately: every session has just been revoked, so
      // the point is to discard all in-memory state rather than to re-render.
      // Ordinary saves elsewhere never do this.
      window.location.assign("/admin");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sign out.");
    }
  }

  return (
    <div className="admin-account-page">
      <h1>Account</h1>

      <section>
        <h2>Change password</h2>
        <form className="admin-form" onSubmit={handleChangePassword}>
          <p className="admin-form__hint">
            Changing your password signs out every device. Minimum 12 characters - length matters
            far more than punctuation.
          </p>
          <div className="admin-form__row">
            <label htmlFor="current-password">Current password</label>
            <input
              id="current-password"
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <div className="admin-form__row">
            <label htmlFor="new-password">New password</label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              autoComplete="new-password"
              minLength={12}
              required
            />
          </div>
          <div className="admin-form__row">
            <label htmlFor="confirm-password">Confirm new password</label>
            <input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
              minLength={12}
              required
            />
          </div>
          <SaveStatus success={notice} error={error} />
          <button type="submit" className="admin-form__submit" disabled={isSubmitting}>
            {isSubmitting ? "Changing..." : "Change password"}
          </button>
        </form>
      </section>

      <section>
        <h2>Sessions</h2>
        <div className="admin-form">
          <p className="admin-form__hint">
            If you have signed in on a device you no longer control, revoke every session. You will
            need to sign in again afterwards.
          </p>
          <button type="button" className="admin-form__submit" onClick={handleSignOutEverywhere}>
            Sign out everywhere
          </button>
        </div>
      </section>
    </div>
  );
}
