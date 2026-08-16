import { Link } from "react-router-dom";

import { useDocumentTitle } from "../hooks/useDocumentTitle";

export default function NotFoundPage() {
  useDocumentTitle("Page not found");
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
