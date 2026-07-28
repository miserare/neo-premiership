import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** Catches render-time errors so one broken component shows a recoverable
 * message instead of blanking the whole site.
 *
 * Must be a class - React has no hook equivalent for componentDidCatch. */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Unhandled render error:", error, info.componentStack);
  }

  handleReset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    const { error } = this.state;
    if (!error) {
      return this.props.children;
    }

    return (
      <div className="error-page">
        <p className="error-page__code">Something went wrong</p>
        <h1>This page hit an unexpected error</h1>
        <p>
          The rest of the site is still fine. Try again, or head back to the league home page.
        </p>
        <div className="error-page__actions">
          {/* A plain anchor, not a router Link: after a render error the tree is
              suspect, so a full reload is the reliable way back. */}
          <a className="error-page__button" href="/">
            Back to home
          </a>
          <button type="button" className="error-page__button" onClick={this.handleReset}>
            Try again
          </button>
        </div>
      </div>
    );
  }
}
