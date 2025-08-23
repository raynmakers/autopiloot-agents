"use client";

import { useState, useCallback, useEffect } from "react";
import { storageOperations } from "@/lib/storage";

interface UploadState {
  status: "idle" | "uploading" | "success" | "error";
  progress: number;
  error: string | null;
  downloadURL: string | null;
}

export function useFileUpload() {
  const [uploadState, setUploadState] = useState<UploadState>({
    status: "idle",
    progress: 0,
    error: null,
    downloadURL: null,
  });

  const uploadFile = useCallback(async (userId: string, file: File) => {
    setUploadState({
      status: "uploading",
      progress: 0,
      error: null,
      downloadURL: null,
    });

    try {
      const { uploadTask, promise } = storageOperations.uploadFileWithProgress(
        userId,
        file,
        (progress) => {
          setUploadState(prev => ({ ...prev, progress }));
        }
      );

      const url = await promise;
      
      setUploadState({
        status: "success",
        progress: 100,
        error: null,
        downloadURL: url,
      });
      
      return url;
    } catch (err: any) {
      setUploadState({
        status: "error",
        progress: 0,
        error: err.message,
        downloadURL: null,
      });
      throw err;
    }
  }, []);

  const uploadAvatar = useCallback(async (userId: string, file: File) => {
    setUploadState({
      status: "uploading",
      progress: 0,
      error: null,
      downloadURL: null,
    });

    try {
      const url = await storageOperations.uploadAvatar(userId, file);
      
      setUploadState({
        status: "success",
        progress: 100,
        error: null,
        downloadURL: url,
      });
      
      return url;
    } catch (err: any) {
      setUploadState({
        status: "error",
        progress: 0,
        error: err.message,
        downloadURL: null,
      });
      throw err;
    }
  }, []);

  const reset = useCallback(() => {
    setUploadState({
      status: "idle",
      progress: 0,
      error: null,
      downloadURL: null,
    });
  }, []);

  return {
    ...uploadState,
    uploadFile,
    uploadAvatar,
    reset,
    // Computed properties for convenience
    isUploading: uploadState.status === "uploading",
    isSuccess: uploadState.status === "success",
    isError: uploadState.status === "error",
    isIdle: uploadState.status === "idle",
  };
}

export function useFileDownload() {
  const [status, setStatus] = useState<"idle" | "downloading" | "success" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  const downloadFile = useCallback(async (filePath: string, fileName?: string) => {
    setStatus("downloading");
    setError(null);

    try {
      const url = await storageOperations.getDownloadURL(filePath);
      
      // Create download link
      const link = document.createElement('a');
      link.href = url;
      link.download = fileName || 'download';
      link.target = '_blank';
      
      // Trigger download
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      setStatus("success");
      return url;
    } catch (err: any) {
      setError(err.message);
      setStatus("error");
      throw err;
    }
  }, []);

  const openFile = useCallback(async (filePath: string) => {
    setStatus("downloading");
    setError(null);

    try {
      const url = await storageOperations.getDownloadURL(filePath);
      window.open(url, '_blank');
      setStatus("success");
      return url;
    } catch (err: any) {
      setError(err.message);
      setStatus("error");
      throw err;
    }
  }, []);

  return {
    status,
    error,
    downloadFile,
    openFile,
    isDownloading: status === "downloading",
    isSuccess: status === "success",
    isError: status === "error",
    isIdle: status === "idle",
  };
}

// Hook for listing files in a folder
export function useFileList(folderPath: string) {
  const [files, setFiles] = useState<string[]>([]);
  const [status, setStatus] = useState<"loading" | "error" | "success">("loading");

  const refreshFiles = useCallback(async () => {
    if (!folderPath) return;
    
    setStatus("loading");
    
    try {
      const fileUrls = await storageOperations.listFiles(folderPath);
      setFiles(fileUrls);
      setStatus("success");
    } catch (error) {
      console.error("Error listing files:", error);
      setFiles([]);
      setStatus("error");
    }
  }, [folderPath]);

  // Auto-refresh on mount and path change
  useEffect(() => {
    refreshFiles();
  }, [refreshFiles]);

  return {
    files,
    status,
    refreshFiles,
    isLoading: status === "loading",
    isError: status === "error",
    isSuccess: status === "success",
  };
}