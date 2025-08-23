// API response wrapper
export interface ApiResponse<T = any> {
  data: T;
  message: string;
  success: boolean;
  timestamp: string;
}

// Error response
export interface ApiError {
  code: string;
  message: string;
  details?: any;
  timestamp: string;
}

// Pagination
export interface PaginationParams {
  page: number;
  limit: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    currentPage: number;
    totalPages: number;
    totalItems: number;
    itemsPerPage: number;
    hasNextPage: boolean;
    hasPrevPage: boolean;
  };
}

// File upload response
export interface FileUploadResponse {
  url: string;
  path: string;
  name: string;
  size: number;
  type: string;
}

// Authentication responses
export interface LoginResponse {
  user: {
    uid: string;
    email: string;
    displayName: string;
    photoURL: string;
    emailVerified: boolean;
  };
  token: string;
  refreshToken: string;
}

export interface SignupResponse extends LoginResponse {
  isNewUser: boolean;
}

// Search/Filter types
export interface SearchParams {
  query?: string;
  filters?: Record<string, any>;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface FilterOption {
  label: string;
  value: string | number | boolean;
  count?: number;
}

// Form validation
export interface ValidationError {
  field: string;
  message: string;
  code: string;
}

export interface FormResponse<T = any> {
  success: boolean;
  data?: T;
  errors?: ValidationError[];
  message?: string;
}