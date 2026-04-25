import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth-guard';
import { guestGuard } from './core/guards/guest-guard';
import { roleGuard } from './core/guards/role-guard';
import { Layout } from './shared/components/layout/layout';

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/login/login').then(m => m.Login)
  },
  {
    path: 'register',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/register/register').then(m => m.Register)
  },
  {
    path: '',
    component: Layout,
    canActivate: [authGuard],
    children: [
      {
        path: 'dashboard',
        canActivate: [roleGuard('ADMIN', 'CORPORATE')],
        loadComponent: () => import('./features/dashboard/dashboard').then(m => m.Dashboard)
      },
      {
        path: 'products',
        loadComponent: () => import('./features/products/products').then(m => m.Products)
      },
      {
        path: 'products/:id',
        loadComponent: () => import('./features/product-detail/product-detail').then(m => m.ProductDetail)
      },
      {
        path: 'orders',
        data: { view: 'orders' },
        loadComponent: () => import('./features/orders/orders').then(m => m.Orders)
      },
      {
        path: 'cart',
        data: { view: 'cart' },
        loadComponent: () => import('./features/orders/orders').then(m => m.Orders)
      },
      {
        path: 'customers',
        canActivate: [roleGuard('ADMIN')],
        loadComponent: () => import('./features/customers/customers').then(m => m.Customers)
      },
      {
        path: 'shipments',
        canActivate: [roleGuard('ADMIN', 'CORPORATE')],
        loadComponent: () => import('./features/shipments/shipments').then(m => m.Shipments)
      },
      {
        path: 'reviews',
        canActivate: [roleGuard('ADMIN', 'CORPORATE')],
        loadComponent: () => import('./features/reviews/reviews').then(m => m.Reviews)
      },
      {
        path: 'analytics',
        canActivate: [roleGuard('ADMIN', 'CORPORATE')],
        loadComponent: () => import('./features/analytics/analytics').then(m => m.Analytics)
      },
      {
        path: 'ai-assistant',
        loadComponent: () => import('./features/ai-assistant/ai-assistant').then(m => m.AiAssistant)
      },
      {
        path: 'store-settings',
        canActivate: [roleGuard('ADMIN', 'CORPORATE')],
        loadComponent: () => import('./features/store-settings/store-settings').then(m => m.StoreSettings)
      },
      {
        path: 'profile',
        loadComponent: () => import('./features/profile/profile').then(m => m.Profile)
      },
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full'
      }
    ]
  },
  {
    path: '**',
    redirectTo: 'login'
  }
];
