import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Auth } from '../services/auth';
import { Role } from '../models/user.model';

export const roleGuard = (...allowedRoles: Role[]): CanActivateFn => {
  return () => {
    const auth = inject(Auth);
    const router = inject(Router);

    if (auth.hasAnyRole(...allowedRoles)) {
      return true;
    }

    router.navigate([auth.getDashboardRoute()]);
    return false;
  };
};
