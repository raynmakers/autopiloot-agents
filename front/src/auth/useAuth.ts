"use client";

import { useEffect, useContext } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { AuthContext } from "./authContext";
import { AuthUser } from "./types";

// Hook to initialize auth listener
export function useAuthInit(
  setUser: (user: AuthUser | null) => void,
  setLoading: (loading: boolean) => void,
  setError: (error: Error | null) => void
) {
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(
      auth,
      (firebaseUser) => {
        if (firebaseUser) {
          const authUser: AuthUser = {
            uid: firebaseUser.uid,
            email: firebaseUser.email,
            displayName: firebaseUser.displayName,
            photoURL: firebaseUser.photoURL,
            emailVerified: firebaseUser.emailVerified,
            isAnonymous: firebaseUser.isAnonymous,
          };
          setUser(authUser);
        } else {
          setUser(null);
        }
        setLoading(false);
      },
      (error) => {
        console.error("Auth state change error:", error);
        setError(error);
        setLoading(false);
      }
    );

    return () => unsubscribe();
  }, [setUser, setLoading, setError]);
}

// Hook to use auth state from context
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}