import { HttpInterceptorFn, HttpErrorResponse, HttpRequest, HttpHandlerFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Observable, catchError, switchMap, throwError, BehaviorSubject, filter, take } from 'rxjs';
import { Auth } from '../services/auth';
import { AuthResponse } from '../models/user.model';

let refreshing = false;
const refreshDone$ = new BehaviorSubject<string | null>(null);

export const jwtInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(Auth);
  const token = auth.getToken();

  if (token && !req.url.includes('/api/auth/')) {
    req = withToken(req, token);
  }

  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      const isAuthCall = req.url.includes('/api/auth/');
      const shouldRetry = (error.status === 401 || error.status === 403) && !isAuthCall;
      if (!shouldRetry) {
        return throwError(() => error);
      }
      return tryRefreshAndRetry(req, next, auth, error);
    })
  );
};

function withToken(req: HttpRequest<unknown>, token: string): HttpRequest<unknown> {
  return req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
}

function tryRefreshAndRetry(
  req: HttpRequest<unknown>,
  next: HttpHandlerFn,
  auth: Auth,
  originalError: HttpErrorResponse,
): Observable<ReturnType<HttpHandlerFn> extends Observable<infer T> ? T : never> {
  if (refreshing) {
    return refreshDone$.pipe(
      filter(t => t !== null),
      take(1),
      switchMap(t => next(withToken(req, t as string))),
    );
  }

  const refresh$ = auth.refreshToken();
  if (!refresh$) {
    auth.logout();
    return throwError(() => originalError);
  }

  refreshing = true;
  refreshDone$.next(null);
  return refresh$.pipe(
    switchMap((res: AuthResponse) => {
      refreshing = false;
      refreshDone$.next(res.accessToken);
      return next(withToken(req, res.accessToken));
    }),
    catchError(err => {
      refreshing = false;
      refreshDone$.next(null);
      auth.logout();
      return throwError(() => err);
    }),
  );
}
