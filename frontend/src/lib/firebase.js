/**
 * Firebase initialization.
 *
 * Config values come from environment variables (see .env.example) rather
 * than being hardcoded here, so you can drop in your own Firebase project's
 * credentials without editing source. Vite only exposes env vars prefixed
 * with VITE_ to client code — see vite.config.js / .env.example.
 *
 * To set this up:
 *   1. Go to https://console.firebase.google.com -> your project (or create one)
 *   2. Project settings -> General -> "Your apps" -> Add a Web app
 *   3. Copy the config values it gives you into frontend/.env (see .env.example)
 *   4. In the Firebase console, go to Authentication -> Sign-in method, and
 *      enable "Email/Password" and "Google" providers.
 */
import { initializeApp } from 'firebase/app'
import { getAuth, GoogleAuthProvider } from 'firebase/auth'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

export const firebaseConfigured = Boolean(firebaseConfig.apiKey && firebaseConfig.projectId)

let app = null
let auth = null
let googleProvider = null

if (firebaseConfigured) {
  app = initializeApp(firebaseConfig)
  auth = getAuth(app)
  googleProvider = new GoogleAuthProvider()
} else {
  // No Firebase config found — auth-dependent UI will show a clear setup
  // notice instead of silently failing or crashing. This lets the rest of
  // the app (and this codebase) remain runnable/demoable before you've
  // wired up your own Firebase project.
  console.warn(
    '[firebase] No VITE_FIREBASE_* environment variables found. ' +
    'Authentication is disabled until you add your Firebase config to frontend/.env — see .env.example.'
  )
}

export { auth, googleProvider }
