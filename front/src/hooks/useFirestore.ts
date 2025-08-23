"use client";

import { useState, useEffect } from "react";
import { 
  collection, 
  doc, 
  onSnapshot, 
  query, 
  where, 
  orderBy,
  limit,
  DocumentData,
  Query
} from "firebase/firestore";
import { db } from "@/lib/firebase";

// Hook for real-time collection subscription
export function useCollection(collectionName: string, userId?: string) {
  const [data, setData] = useState<any[]>([]);
  const [status, setStatus] = useState<"loading" | "error" | "success">("loading");

  useEffect(() => {
    if (!db || Object.keys(db).length === 0) {
      setStatus("error");
      return;
    }

    setStatus("loading");

    let q: Query<DocumentData> = collection(db, collectionName);
    
    // Add user filter if provided
    if (userId) {
      q = query(q, where("ownerUid", "==", userId));
    }

    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        const documents = snapshot.docs.map(doc => ({
          id: doc.id,
          ...doc.data()
        }));
        setData(documents);
        setStatus("success");
      },
      (error) => {
        console.error(`Error fetching ${collectionName}:`, error);
        setData([]);
        setStatus("error");
      }
    );

    return () => unsubscribe();
  }, [collectionName, userId]);

  return { data, status };
}

// Hook for real-time document subscription
export function useDocument<T = any>(collectionName: string, documentId: string | null | undefined) {
  const [data, setData] = useState<T | undefined>(undefined);
  const [status, setStatus] = useState<"loading" | "error" | "success">("loading");

  useEffect(() => {
    if (!documentId) {
      setData(undefined);
      setStatus("error");
      return;
    }

    if (!db || Object.keys(db).length === 0) {
      setStatus("error");
      return;
    }

    setStatus("loading");

    const docRef = doc(db, collectionName, documentId);

    const unsubscribe = onSnapshot(
      docRef,
      (snapshot) => {
        if (snapshot.exists()) {
          setData(snapshot.data() as T);
          setStatus("success");
        } else {
          setData(undefined);
          setStatus("error");
        }
      },
      (error) => {
        console.error(`Error fetching document ${documentId}:`, error);
        setData(undefined);
        setStatus("error");
      }
    );

    return () => unsubscribe();
  }, [collectionName, documentId]);

  return { data, status };
}

// Hook for filtered collection subscription with pagination
interface UseFilteredCollectionProps {
  collectionName: string;
  userId?: string;
  filters?: { field: string; operator: any; value: any }[];
  orderByField?: string;
  orderDirection?: 'asc' | 'desc';
  limitCount?: number;
  trigger?: any[]; // For dependency tracking
}

export function useFilteredCollection({
  collectionName,
  userId,
  filters = [],
  orderByField,
  orderDirection = 'desc',
  limitCount,
  trigger = []
}: UseFilteredCollectionProps) {
  const [data, setData] = useState<any[]>([]);
  const [status, setStatus] = useState<"loading" | "error" | "success">("loading");
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    if (!db || Object.keys(db).length === 0) {
      setStatus("error");
      return;
    }

    setStatus("loading");

    let q: Query<DocumentData> = collection(db, collectionName);

    // Add user filter if provided
    if (userId) {
      q = query(q, where("ownerUid", "==", userId));
    }

    // Apply additional filters
    filters.forEach(filter => {
      q = query(q, where(filter.field, filter.operator, filter.value));
    });

    // Apply ordering
    if (orderByField) {
      q = query(q, orderBy(orderByField, orderDirection));
    }

    // Apply limit
    if (limitCount) {
      q = query(q, limit(limitCount));
    }

    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        const documents = snapshot.docs.map(doc => ({
          id: doc.id,
          ...doc.data()
        }));
        setData(documents);
        setTotalCount(snapshot.size);
        setStatus("success");
      },
      (error) => {
        console.error(`Error fetching filtered ${collectionName}:`, error);
        setData([]);
        setStatus("error");
      }
    );

    return () => unsubscribe();
  }, [
    collectionName, 
    userId, 
    JSON.stringify(filters), 
    orderByField, 
    orderDirection, 
    limitCount, 
    trigger?.length
  ]);

  return { data, status, totalCount };
}