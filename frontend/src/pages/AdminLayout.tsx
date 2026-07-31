import { type FormEvent, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useAdminSession } from "../hooks/useAdminSession";
import { ApiError, getAuthFailureMessage } from "../lib/api";

export default function AdminLayout() {
  const { session, isLoading, signIn, signOut } = useAdminSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [signInError, setSignInError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!username.trim() || !password) return;

    setSignInError(null);
    setIsSubmitting(true);
    try {
      await signIn(username.trim(), password);
      // Never keep the password around after it has been exchanged for a session.
      setPassword("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setSignInError("Too many failed attempts. Wait a few minutes and try again.");
      } else if (err instanceof ApiError && err.status === 401) {
        // Mirrors the server's nondisclosing message: never reveal whether the
        // username exists.
        setSignInError("Invalid username or password.");
      } else if (err instanceof ApiError) {
        setSignInError(err.message);
      } else {
        setSignInError("Could not reach the server. Check your connection.");
      }
      setPassword("");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return (
      <div className="admin-page">
        <p role="status">Checking your session...</p>
      </div>
    );
  }

  if (!session) {
    const expiredMessage = getAuthFailureMessage();
    return (
      <div className="admin-page">
        <h1>Administrator Sign In</h1>
        {expiredMessage && !signInError && (
          <p role="alert" className="admin-page__error">
            {expiredMessage}
          </p>
        )}
        <form className="admin-form admin-login-form" onSubmit={handleSubmit}>
          <div className="admin-form__row">
            <label htmlFor="admin-username">Username</label>
            <input
              id="admin-username"
              name="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
            />
          </div>
          <div className="admin-form__row">
            <label htmlFor="admin-password">Password</label>
            <input
              id="admin-password"
              name="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          {signInError && (
            <p role="alert" className="admin-form__error">
              {signInError}
            </p>
          )}
          <button type="submit" className="admin-form__submit" disabled={isSubmitting}>
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
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
          <NavLink to="/admin/account">Account</NavLink>
        </nav>
        <div className="admin-page__identity">
          <span className="admin-page__user">{session.username}</span>
          <button type="button" className="admin-page__sign-out" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </div>
      <Outlet />
    </div>
  );
}
