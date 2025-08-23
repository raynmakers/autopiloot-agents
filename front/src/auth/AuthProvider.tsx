"use client";

import { useState, useCallback, ReactNode } from "react";
import { AuthContext, AuthContextType } from "./authContext";
import { AuthUser } from "./types";
import { useAuthInit } from "./useAuth";

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const isAuthenticated = !loading && user !== null && user.emailVerified;
  const isAnonymous = user?.isAnonymous ?? false;

  const contextValue: AuthContextType = {
    user,
    loading,
    error,
    isAuthenticated,
    isAnonymous,
    setUser: useCallback((user: AuthUser | null) => setUser(user), []),
    setLoading: useCallback((loading: boolean) => setLoading(loading), []),
    setError: useCallback((error: Error | null) => setError(error), []),
  };

  // Initialize auth listener
  useAuthInit(contextValue.setUser, contextValue.setLoading, contextValue.setError);

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
}