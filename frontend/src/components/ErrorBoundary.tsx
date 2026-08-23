import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * A crash anywhere below this (most commonly a stale/incompatible wallet
 * reconnect session in localStorage throwing during mount) used to unmount
 * the entire React tree, taking the header down with it. This boundary
 * catches that instead of showing a blank page, and offers a reset that
 * clears wallet session storage — the most common cause of a stuck crash.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: { componentStack: string }) {
    // eslint-disable-next-line no-console
    console.error('Unhandled render error:', error, info.componentStack);
  }

  handleReset = () => {
    try {
      Object.keys(localStorage)
        .filter((k) => /wallet/i.test(k))
        .forEach((k) => localStorage.removeItem(k));
    } catch {
      // ignore
    }
    window.location.reload();
  };

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 16,
            padding: 24,
            textAlign: 'center',
            fontFamily: 'var(--grotesk, sans-serif)',
          }}
        >
          <h1 style={{ fontSize: 22 }}>Something went wrong.</h1>
          <p style={{ color: 'var(--text-muted, #666)', maxWidth: 420 }}>
            The app hit an unexpected error, often caused by a stale wallet connection. Resetting
            clears the saved wallet session and reloads the page.
          </p>
          <button
            type="button"
            onClick={this.handleReset}
            className="btn btn-accent"
            style={{ padding: '10px 20px' }}
          >
            Reset and reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
