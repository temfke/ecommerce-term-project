import { Component, ChangeDetectionStrategy, computed, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { Auth } from '../../../core/services/auth';
import { Cart } from '../../../core/services/cart';

interface NavItem {
  label: string;
  route: string;
  icon: string;
  roles: string[];
}

@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Sidebar {
  private readonly auth = inject(Auth);
  readonly cart = inject(Cart);

  readonly collapsed = signal(false);

  private readonly allNavItems: NavItem[] = [
    { label: 'Dashboard', route: '/dashboard', icon: '📊', roles: ['ADMIN', 'CORPORATE'] },
    { label: 'Products', route: '/products', icon: '📦', roles: ['ADMIN', 'CORPORATE', 'INDIVIDUAL'] },
    { label: 'Orders', route: '/orders', icon: '🛒', roles: ['ADMIN', 'CORPORATE', 'INDIVIDUAL'] },
    { label: 'Customers', route: '/customers', icon: '👥', roles: ['ADMIN'] },
    { label: 'Shipments', route: '/shipments', icon: '🚚', roles: ['ADMIN', 'CORPORATE'] },
    { label: 'Reviews', route: '/reviews', icon: '⭐', roles: ['ADMIN', 'CORPORATE'] },
    { label: 'Analytics', route: '/analytics', icon: '📈', roles: ['ADMIN', 'CORPORATE'] },
    { label: 'Store Settings', route: '/store-settings', icon: '🏪', roles: ['CORPORATE'] },
    { label: 'User Management', route: '/user-management', icon: '🔧', roles: ['ADMIN'] },
  ];

  readonly navItems = computed(() => {
    const role = this.auth.userRole();
    if (!role) return [];
    return this.allNavItems.filter(item => item.roles.includes(role));
  });

  toggle() {
    this.collapsed.update(v => !v);
  }
}
