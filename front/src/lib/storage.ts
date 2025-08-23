"use client";

import {
  ref,
  uploadBytes,
  uploadBytesResumable,
  getDownloadURL,
  deleteObject,
  listAll,
  UploadTask,
} from "firebase/storage";
import { storage } from "./firebase";

// Storage paths
const storagePaths = {
  userAvatar: (userId: string) => `users/${userId}/avatar`,
  userFiles: (userId: string, fileName: string) => `users/${userId}/files/${fileName}`,
};

// Storage operations
export const storageOperations = {
  // Upload user avatar
  async uploadAvatar(userId: string, file: File): Promise<string> {
    try {
      const storageRef = ref(storage, storagePaths.userAvatar(userId));
      const snapshot = await uploadBytes(storageRef, file);
      const downloadURL = await getDownloadURL(snapshot.ref);
      return downloadURL;
    } catch (error) {
      console.error("Error uploading avatar:", error);
      throw error;
    }
  },

  // Upload file with progress tracking
  uploadFileWithProgress(
    userId: string,
    file: File,
    onProgress?: (progress: number) => void
  ): {
    uploadTask: UploadTask;
    promise: Promise<string>;
  } {
    const fileName = `${Date.now()}_${file.name}`;
    const storageRef = ref(storage, storagePaths.userFiles(userId, fileName));
    const uploadTask = uploadBytesResumable(storageRef, file);

    const promise = new Promise<string>((resolve, reject) => {
      uploadTask.on(
        "state_changed",
        (snapshot) => {
          const progress = (snapshot.bytesTransferred / snapshot.totalBytes) * 100;
          onProgress?.(progress);
        },
        (error) => {
          console.error("Upload error:", error);
          reject(error);
        },
        async () => {
          try {
            const downloadURL = await getDownloadURL(uploadTask.snapshot.ref);
            resolve(downloadURL);
          } catch (error) {
            reject(error);
          }
        }
      );
    });

    return { uploadTask, promise };
  },

  // Delete file
  async deleteFile(filePath: string): Promise<void> {
    try {
      const fileRef = ref(storage, filePath);
      await deleteObject(fileRef);
    } catch (error) {
      console.error("Error deleting file:", error);
      throw error;
    }
  },

  // List all files in a folder
  async listFiles(folderPath: string): Promise<string[]> {
    try {
      const folderRef = ref(storage, folderPath);
      const result = await listAll(folderRef);
      
      const urls = await Promise.all(
        result.items.map(async (itemRef) => {
          return getDownloadURL(itemRef);
        })
      );
      
      return urls;
    } catch (error) {
      console.error("Error listing files:", error);
      return [];
    }
  },

  // Get download URL from path
  async getDownloadURL(filePath: string): Promise<string> {
    try {
      const fileRef = ref(storage, filePath);
      return await getDownloadURL(fileRef);
    } catch (error) {
      console.error("Error getting download URL:", error);
      throw error;
    }
  },
};