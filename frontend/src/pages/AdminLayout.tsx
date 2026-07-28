import { type FormEvent, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useAdminToken } from "../hooks/useAdminToken";
import { api, ApiError, getAuthFailureMessage } from "../lib/api";

export default function AdminLayout() {
  const { token, saveToken, clearToken } = useAdminToken();
  const [tokenInput, setTokenInput] = useState("");
  const [signInError, setSignInError] = useState<string | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const candidate = tokenInput.trim();
    if (!candidate) return;

    setSignInError(null);
    setIsVerifying(true);
    try {
      // Check the token before storing it - otherwise any string "signs you in"
      // and the first save is what discovers the token was wrong.
      await api.admin.verify(candidate);
      saveToken(candidate);
      setTokenInput("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setSignInError(`${err.message}. Set ADMIN_TOKEN in the backend environment and restart it.`);
      } else if (err instanceof ApiError && err.status === 401) {
        setSignInError(`${err.message}. Check the ADMIN_TOKEN value the backend was started with.`);
      } else if (err instanceof ApiError) {
        setSignInError(err.message);
      } else {
        setSignInError("Could not reach the server to check that token.");
      }
    } finally {
      setIsVerifying(false);
    }
  }

  if (!token) {
    const rejectedMessage = getAuthFailureMessage();
    return (
      <div className="admin-page">
        <h1>Admin Sign In</h1>
        <p>Enter the admin token to manage the league.</p>
        {rejectedMessage && !signInError && (
          <p role="alert" className="admin-page__error">
            {rejectedMessage}
          </p>
        )}
        <form className="admin-token-form" onSubmit={handleSubmit}>
          <label className="admin-token-form__label" htmlFor="admin-token-input">
            Admin token
          </label>
          <div className="admin-token-form__row">
            <input
              id="admin-token-input"
              type="password"
              className="admin-token-form__input"
              value={tokenInput}
              onChange={(event) => setTokenInput(event.target.value)}
              autoComplete="off"
            />
            <button type="submit" className="admin-token-form__button" disabled={isVerifying}>
              {isVerifying ? "Checking..." : "Sign in"}
            </button>
          </div>
          {signInError && (
            <p role="alert" className="admin-form__error">
              {signInError}
            </p>
          )}
        </form>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <div className="admin-page__header">
        <nav className="admin-page__nav">
          <NavLink to="/admin/players">Players</NavLink>
          <NavLink to="/admin/seasons">Seasons</NavLink>
          <NavLink to="/admin/matches">Matches</NavLink>
          <NavLink to="/admin/site">Site</NavLink>
        </nav>
        <button type="button" className="admin-page__sign-out" onClick={clearToken}>
          Sign out
        </button>
      </div>
      <Outlet />
    </div>
  );
}
