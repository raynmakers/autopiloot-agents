"use client";

import { initializeApp, FirebaseApp } from "firebase/app";
import { getAuth, Auth } from "firebase/auth";
import { getFirestore, Firestore } from "firebase/firestore";
import { getFunctions, Functions, connectFunctionsEmulator } from "firebase/functions";
import { getStorage, FirebaseStorage } from "firebase/storage";
import { getAnalytics, Analytics } from "firebase/analytics";
import { FIREBASE_CONFIG } from "@/config";

// Initialize Firebase only if config is available
let firebaseApp: FirebaseApp | undefined;

if (FIREBASE_CONFIG.apiKey) {
  firebaseApp = initializeApp(FIREBASE_CONFIG);
}

// Firebase services (only initialize if app exists)
export const auth = firebaseApp ? getAuth(firebaseApp) : {} as Auth;
export const db = firebaseApp ? getFirestore(firebaseApp) : {} as Firestore;
export const storage = firebaseApp ? getStorage(firebaseApp) : {} as FirebaseStorage;
export const functions = firebaseApp ? getFunctions(firebaseApp) : {} as Functions;

// Analytics (client-side only)
export let analytics: Analytics | undefined = undefined;
if (typeof window !== "undefined" && firebaseApp) {
  analytics = getAnalytics(firebaseApp);
}


// Development environment emulators (optional)
if (process.env.NODE_ENV === "development") {
  // Uncomment to use emulators in development
  // connectFunctionsEmulator(functions, "localhost", 5001);
  // connectAuthEmulator(auth, "http://localhost:9099/");
  // connectFirestoreEmulator(db, "localhost", 8080);
  // connectStorageEmulator(storage, "localhost", 9199);
}