"use client";

import {
  collection,
  doc,
  getDoc,
  setDoc,
  updateDoc,
  deleteDoc,
  query,
  where,
  getDocs,
  DocumentData,
  CollectionReference,
  DocumentReference,
  Timestamp,
  serverTimestamp,
} from "firebase/firestore";
import { db } from "./firebase";

// Example user type
export interface UserDoc extends DocumentData {
  uid: string;
  email?: string;
  displayName?: string;
  photoURL?: string;
  createdAt?: Timestamp;
  updatedAt?: Timestamp;
}

// Collection references (only create if db is initialized)
export const collections = {
  get users() {
    if (!db || Object.keys(db).length === 0) {
      return {} as CollectionReference<UserDoc>;
    }
    return collection(db, "users") as CollectionReference<UserDoc>;
  },
};

// User operations
export const userOperations = {
  // Get user by ID
  async getById(uid: string): Promise<UserDoc | null> {
    try {
      const userRef = doc(collections.users, uid);
      const userSnap = await getDoc(userRef);
      
      if (!userSnap.exists()) {
        return null;
      }
      
      return userSnap.data() as UserDoc;
    } catch (error) {
      console.error("Error fetching user:", error);
      return null;
    }
  },

  // Create user document
  async create(uid: string, data: Partial<UserDoc>): Promise<void> {
    const userRef = doc(collections.users, uid);
    await setDoc(userRef, {
      uid,
      ...data,
      createdAt: serverTimestamp(),
      updatedAt: serverTimestamp(),
    });
  },

  // Update user document
  async update(uid: string, data: Partial<UserDoc>): Promise<void> {
    const userRef = doc(collections.users, uid);
    await updateDoc(userRef, {
      ...data,
      updatedAt: serverTimestamp(),
    });
  },

  // Delete user document
  async delete(uid: string): Promise<void> {
    const userRef = doc(collections.users, uid);
    await deleteDoc(userRef);
  },

  // Get users by query
  async getByQuery(field: string, operator: any, value: any): Promise<UserDoc[]> {
    try {
      const q = query(collections.users, where(field, operator, value));
      const querySnapshot = await getDocs(q);
      
      const users: UserDoc[] = [];
      querySnapshot.forEach((doc) => {
        users.push(doc.data() as UserDoc);
      });
      
      return users;
    } catch (error) {
      console.error("Error querying users:", error);
      return [];
    }
  },
};