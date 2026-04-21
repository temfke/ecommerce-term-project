export type Role = 'ADMIN' | 'CORPORATE' | 'INDIVIDUAL';

export interface User {
  id: number;
  email: string;
  firstName: string;
  lastName: string;
  role: Role;
  gender?: string;
  phone?: string;
  enabled: boolean;
  emailVerified: boolean;
  createdAt: string;
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  userId: number;
  email: string;
  firstName: string;
  lastName: string;
  role: Role;
  emailVerified: boolean;
  emailVerificationToken?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
  role: Role;
  gender?: string;
  phone?: string;
}
