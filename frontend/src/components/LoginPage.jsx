import { signInWithPopup } from "firebase/auth";
import { auth, googleProvider } from "../lib/firebase";
import { authCallback } from "../lib/api";
import { useState } from "react";
import "./LoginPage.css";

export default function LoginPage({ configWarning }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);


  const handleLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await signInWithPopup(auth, googleProvider);
      const idToken = await result.user.getIdToken();

      // Firebase popup gives us the Google OAuth access token directly
      // (not an authorization code). Extract it from the credential.
      const oauthAccessToken =
        result._tokenResponse?.oauthAccessToken || null;

      if (idToken) {
        try {
          await authCallback(idToken, oauthAccessToken);
        } catch (backendErr) {
          console.warn("Backend auth callback failed:", backendErr.message);
          // Continue anyway - user is authenticated via Firebase
        }
      }
    } catch (err) {
      if (err.code !== "auth/popup-closed-by-user") {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-card">
          <div className="login-icon">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <rect width="48" height="48" rx="12" fill="url(#grad)" />
              <path d="M14 24l6 6 14-14" stroke="#fff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
              <defs>
                <linearGradient id="grad" x1="0" y1="0" x2="48" y2="48">
                  <stop stopColor="#34D399"/>
                  <stop offset="1" stopColor="#FB923C"/>
                </linearGradient>
              </defs>
            </svg>
          </div>

          <h1 className="login-title">Job Tracker</h1>
          <p className="login-subtitle">
            AI-powered job application tracking.<br />
            Connect your Gmail and let Claude organize your job hunt.
          </p>

          <button
            className="login-btn"
            onClick={handleLogin}
            disabled={loading || configWarning}
            id="google-sign-in-btn"
          >
            {loading ? (
              <span className="login-spinner" />
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
              </svg>
            )}
            {loading ? "Connecting..." : "Sign in with Google"}
          </button>

          {configWarning && (
            <div className="login-config-warning">
              ⚠️ Firebase not configured. Copy <code>.env.local.example</code> to <code>.env.local</code> and add your Firebase keys.
            </div>
          )}

          {error && <p className="login-error">{error}</p>}

          <div className="login-features">
            <div className="login-feature">
              <span className="feature-icon">📧</span>
              <span>Reads your Gmail automatically</span>
            </div>
            <div className="login-feature">
              <span className="feature-icon">🤖</span>
              <span>AI classifies every email</span>
            </div>
            <div className="login-feature">
              <span className="feature-icon">📊</span>
              <span>Live dashboard & analytics</span>
            </div>
          </div>
        </div>

        <p className="login-footer">
          Your emails are processed securely. We only read job-related messages.
        </p>
      </div>
    </div>
  );
}
