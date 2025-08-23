import { User } from "firebase/auth";

export interface AuthUser {
  uid: string;
  email: string | null;
  displayName: string | null;
  photoURL: string | null;
  emailVerified: boolean;
  isAnonymous: boolean;
}

export interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  error: Error | null;
}