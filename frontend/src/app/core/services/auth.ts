import { inject, Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';
import { AuthResponse, LoginRequest, RegisterRequest, Role } from '../models/user.model';

@Injectable({ providedIn: 'root' })
export class Auth {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly API = 'http://localhost:8080/api/auth';

  private readonly _token = signal<string | null>(localStorage.getItem('accessToken'));
  private readonly _refreshToken = signal<string | null>(localStorage.getItem('refreshToken'));
  private readonly _user = signal<AuthResponse | null>(this.loadUser());

  readonly isAuthenticated = computed(() => !!this._token());
  readonly currentUser = computed(() => this._user());
  readonly userRole = computed(() => this._user()?.role ?? null);

  login(request: LoginRequest) {
    return this.http.post<AuthResponse>(`${this.API}/login`, request).pipe(
      tap(res => this.storeAuth(res))
    );
  }

  register(request: RegisterRequest) {
    return this.http.post<AuthResponse>(`${this.API}/register`, request).pipe(
      tap(res => this.storeAuth(res))
    );
  }

  refreshToken() {
    const refreshToken = this._refreshToken();
    if (!refreshToken) return;
    return this.http.post<AuthResponse>(`${this.API}/refresh`, { refreshToken }).pipe(
      tap(res => this.storeAuth(res))
    );
  }

  logout() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
    this._token.set(null);
    this._refreshToken.set(null);
    this._user.set(null);
    this.router.navigate(['/login']);
  }

  getToken(): string | null {
    return this._token();
  }

  hasRole(role: Role): boolean {
    return this._user()?.role === role;
  }

  hasAnyRole(...roles: Role[]): boolean {
    const userRole = this._user()?.role;
    return userRole != null && roles.includes(userRole);
  }

  getDashboardRoute(): string {
    return this._user()?.role === 'INDIVIDUAL' ? '/products' : '/dashboard';
  }

  updateStoredAuth(res: AuthResponse) {
    this.storeAuth(res);
  }

  private storeAuth(res: AuthResponse) {
    localStorage.setItem('accessToken', res.accessToken);
    localStorage.setItem('refreshToken', res.refreshToken);
    localStorage.setItem('user', JSON.stringify(res));
    this._token.set(res.accessToken);
    this._refreshToken.set(res.refreshToken);
    this._user.set(res);
  }

  private loadUser(): AuthResponse | null {
    const data = localStorage.getItem('user');
    if (!data) return null;
    try {
      return JSON.parse(data) as AuthResponse;
    } catch {
      return null;
    }
  }
}
