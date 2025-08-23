"use client";

import { createContext } from "react";
import { AuthUser, AuthState } from "./types";

export interface AuthContextType extends AuthState {
  setUser: (user: AuthUser | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: Error | null) => void;
  isAuthenticated: boolean;
  isAnonymous: boolean;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);