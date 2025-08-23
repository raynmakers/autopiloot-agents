import { Timestamp } from "firebase/firestore";

// Base document interface
export interface BaseDocument {
  id: string;
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

// User document interface
export interface UserDoc extends BaseDocument {
  uid: string;
  email?: string;
  displayName?: string;
  photoURL?: string;
  emailVerified: boolean;
  isAnonymous: boolean;
  // Add custom user fields as needed
  role?: 'admin' | 'user' | 'moderator';
  preferences?: {
    theme: 'light' | 'dark';
    language: string;
    notifications: boolean;
  };
}

// Example: Post document interface
export interface PostDoc extends BaseDocument {
  title: string;
  content: string;
  authorId: string;
  authorName: string;
  published: boolean;
  tags: string[];
  likes: number;
  views: number;
}

// Example: Comment document interface
export interface CommentDoc extends BaseDocument {
  postId: string;
  content: string;
  authorId: string;
  authorName: string;
  parentCommentId?: string; // For nested comments
}

// File upload metadata
export interface FileDoc extends BaseDocument {
  name: string;
  size: number;
  type: string;
  url: string;
  path: string;
  uploadedBy: string;
}

// Notification document
export interface NotificationDoc extends BaseDocument {
  userId: string;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  read: boolean;
  actionUrl?: string;
}

// Settings document
export interface SettingsDoc {
  userId: string;
  theme: 'light' | 'dark';
  language: string;
  notifications: {
    email: boolean;
    push: boolean;
    inApp: boolean;
  };
  privacy: {
    profileVisible: boolean;
    activityVisible: boolean;
  };
  updatedAt: Timestamp;
}

// Collection names as constants
export const COLLECTIONS = {
  USERS: 'users',
  POSTS: 'posts',
  COMMENTS: 'comments',
  FILES: 'files',
  NOTIFICATIONS: 'notifications',
  SETTINGS: 'settings',
} as const;

// Type for collection names
export type CollectionName = typeof COLLECTIONS[keyof typeof COLLECTIONS];