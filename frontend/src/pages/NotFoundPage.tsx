import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="error-page">
      <p className="error-page__code">404</p>
      <h1>Page not found</h1>
      <p>That page doesn&apos;t exist. It may have been renamed, or the link may be wrong.</p>
      <div className="error-page__actions">
        <Link className="error-page__button" to="/">
          Back to home
        </Link>
        <Link className="error-page__button" to="/seasons">
          Browse seasons
        </Link>
      </div>
    </div>
  );
}
