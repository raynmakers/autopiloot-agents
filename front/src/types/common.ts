// Common utility types
export type ID = string;

// Loading states
export interface LoadingState {
  loading: boolean;
  error: Error | null;
}

// Generic data state
export interface DataState<T> extends LoadingState {
  data: T | null;
}

// Form state
export interface FormState {
  isSubmitting: boolean;
  isDirty: boolean;
  isValid: boolean;
  errors: Record<string, string>;
}

// File types
export interface FileWithPreview extends File {
  preview: string;
  id?: string;
}

export interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  url: string;
  uploadedAt: Date;
}

// Theme types
export type ThemeMode = 'light' | 'dark';

export interface ThemeSettings {
  mode: ThemeMode;
  primaryColor: string;
  fontFamily: string;
}

// Navigation
export interface NavItem {
  title: string;
  path: string;
  icon?: string;
  children?: NavItem[];
  disabled?: boolean;
  external?: boolean;
}

// Table/List types
export interface SortConfig {
  field: string;
  direction: 'asc' | 'desc';
}

export interface TableColumn<T = any> {
  id: string;
  label: string;
  minWidth?: number;
  align?: 'left' | 'center' | 'right';
  sortable?: boolean;
  format?: (value: any, row?: T) => React.ReactNode;
}

// Modal/Dialog types
export interface ModalState {
  open: boolean;
  data?: any;
}

// Notification types
export type NotificationType = 'success' | 'error' | 'warning' | 'info';

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  actionUrl?: string;
}

// Utility types
export type ValueOf<T> = T[keyof T];
export type Optional<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>;
export type RequiredFields<T, K extends keyof T> = T & Required<Pick<T, K>>;

// Event handler types
export type EventHandler<T = Event> = (event: T) => void;
export type AsyncEventHandler<T = Event> = (event: T) => Promise<void>;

// Generic CRUD operations
export interface CrudOperations<T, CreateData = Partial<T>, UpdateData = Partial<T>> {
  create: (data: CreateData) => Promise<T>;
  read: (id: ID) => Promise<T | null>;
  update: (id: ID, data: UpdateData) => Promise<T>;
  delete: (id: ID) => Promise<void>;
  list: (params?: any) => Promise<T[]>;
}