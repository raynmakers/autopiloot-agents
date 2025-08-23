"use client";

import { httpsCallable, HttpsCallableResult } from "firebase/functions";
import { functions } from "./firebase";

// Example function types
export interface ExampleRequest {
  message: string;
}

export interface ExampleResponse {
  result: string;
}

// Callable functions wrapper
export const callableFunctions = {
  // Example callable function
  exampleFunction: async (data: ExampleRequest): Promise<ExampleResponse> => {
    const callable = httpsCallable<ExampleRequest, ExampleResponse>(
      functions,
      "exampleFunction"
    );
    const result = await callable(data);
    return result.data;
  },
};

// Generic callable function helper
export async function callFunction<TRequest, TResponse>(
  functionName: string,
  data: TRequest
): Promise<TResponse> {
  const callable = httpsCallable<TRequest, TResponse>(functions, functionName);
  const result = await callable(data);
  return result.data;
}