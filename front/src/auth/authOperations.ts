"use client";

import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  sendPasswordResetEmail,
  updateProfile,
  signInWithPopup,
  GoogleAuthProvider,
  signInAnonymously,
  User,
  sendEmailVerification,
} from "firebase/auth";
import { auth } from "@/lib/firebase";
import { userOperations } from "@/lib/firestore";

// Auth operations
export const authOperations = {
  // Sign in with email and password
  async signIn(email: string, password: string) {
    try {
      const result = await signInWithEmailAndPassword(auth, email, password);
      return result.user;
    } catch (error) {
      console.error("Sign in error:", error);
      throw error;
    }
  },

  // Sign up with email and password
  async signUp(email: string, password: string, displayName?: string) {
    try {
      const result = await createUserWithEmailAndPassword(auth, email, password);
      
      // Update display name if provided
      if (displayName) {
        await updateProfile(result.user, { displayName });
      }

      // Send verification email
      await sendEmailVerification(result.user);

      // Create user document in Firestore
      await userOperations.create(result.user.uid, {
        uid: result.user.uid,
        email: result.user.email || undefined,
        displayName: displayName || result.user.displayName || undefined,
        photoURL: result.user.photoURL || undefined,
      });

      return result.user;
    } catch (error) {
      console.error("Sign up error:", error);
      throw error;
    }
  },

  // Sign in with Google
  async signInWithGoogle() {
    try {
      const provider = new GoogleAuthProvider();
      const result = await signInWithPopup(auth, provider);
      
      // Check if this is a new user
      const existingUser = await userOperations.getById(result.user.uid);
      if (!existingUser) {
        // Create user document for new Google users
        await userOperations.create(result.user.uid, {
          uid: result.user.uid,
          email: result.user.email || undefined,
          displayName: result.user.displayName || undefined,
          photoURL: result.user.photoURL || undefined,
        });
      }

      return result.user;
    } catch (error) {
      console.error("Google sign in error:", error);
      throw error;
    }
  },

  // Sign in anonymously
  async signInAnonymously() {
    try {
      const result = await signInAnonymously(auth);
      return result.user;
    } catch (error) {
      console.error("Anonymous sign in error:", error);
      throw error;
    }
  },

  // Sign out
  async signOut() {
    try {
      await signOut(auth);
    } catch (error) {
      console.error("Sign out error:", error);
      throw error;
    }
  },

  // Send password reset email
  async sendPasswordResetEmail(email: string) {
    try {
      await sendPasswordResetEmail(auth, email);
    } catch (error) {
      console.error("Password reset error:", error);
      throw error;
    }
  },

  // Update user profile
  async updateProfile(user: User, profile: { displayName?: string; photoURL?: string }) {
    try {
      await updateProfile(user, profile);
      
      // Update Firestore document
      await userOperations.update(user.uid, profile);
    } catch (error) {
      console.error("Profile update error:", error);
      throw error;
    }
  },

  // Send email verification
  async sendEmailVerification(user: User) {
    try {
      await sendEmailVerification(user);
    } catch (error) {
      console.error("Email verification error:", error);
      throw error;
    }
  },
};