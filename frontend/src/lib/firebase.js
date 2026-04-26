import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "demo-key",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "demo.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "demo-project",
};

export const isConfigured = !!(
  import.meta.env.VITE_FIREBASE_API_KEY &&
  import.meta.env.VITE_FIREBASE_PROJECT_ID
);

let app, auth, db, googleProvider;

try {
  app = initializeApp(firebaseConfig);
  auth = getAuth(app);
  db = getFirestore(app);

  googleProvider = new GoogleAuthProvider();
  // Request Gmail readonly scope alongside login
  googleProvider.addScope("https://www.googleapis.com/auth/gmail.readonly");
  // Force consent to ensure we get a refresh token
  googleProvider.setCustomParameters({
    access_type: "offline",
    prompt: "consent",
  });
} catch (err) {
  console.error("Firebase initialization failed:", err);
}

export { auth, db, googleProvider };
