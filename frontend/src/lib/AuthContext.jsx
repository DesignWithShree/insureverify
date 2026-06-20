import React, { createContext, useContext, useEffect, useState } from 'react'
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut as firebaseSignOut,
  onAuthStateChanged,
} from 'firebase/auth'
import { auth, googleProvider, firebaseConfigured } from './firebase.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(firebaseConfigured)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!firebaseConfigured) {
      setLoading(false)
      return
    }
    const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
      setUser(firebaseUser)
      setLoading(false)
    })
    return unsubscribe
  }, [])

  const clearError = () => setError(null)

  const signUpWithEmail = async (email, password) => {
    setError(null)
    try {
      const cred = await createUserWithEmailAndPassword(auth, email, password)
      return cred.user
    } catch (e) {
      setError(friendlyAuthError(e))
      throw e
    }
  }

  const signInWithEmail = async (email, password) => {
    setError(null)
    try {
      const cred = await signInWithEmailAndPassword(auth, email, password)
      return cred.user
    } catch (e) {
      setError(friendlyAuthError(e))
      throw e
    }
  }

  const signInWithGoogle = async () => {
    setError(null)
    try {
      const cred = await signInWithPopup(auth, googleProvider)
      return cred.user
    } catch (e) {
      setError(friendlyAuthError(e))
      throw e
    }
  }

  const signOut = () => firebaseSignOut(auth)

  return (
    <AuthContext.Provider value={{
      user, loading, error, clearError,
      signUpWithEmail, signInWithEmail, signInWithGoogle, signOut,
      firebaseConfigured,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

function friendlyAuthError(e) {
  const code = e?.code || ''
  const map = {
    'auth/email-already-in-use': 'An account with this email already exists. Try signing in instead.',
    'auth/invalid-email': 'That email address looks invalid.',
    'auth/weak-password': 'Password should be at least 6 characters.',
    'auth/user-not-found': 'No account found with that email.',
    'auth/wrong-password': 'Incorrect password.',
    'auth/invalid-credential': 'Incorrect email or password.',
    'auth/popup-closed-by-user': 'Sign-in popup was closed before completing.',
    'auth/network-request-failed': 'Network error — check your connection and try again.',
  }
  return map[code] || 'Something went wrong with sign-in. Please try again.'
}
