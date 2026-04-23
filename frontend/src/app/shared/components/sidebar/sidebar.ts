import { Component, ChangeDetectionStrategy, computed, inject, signal } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { Auth } from '../../../core/services/auth';
import { Cart } from '../../../core/services/cart';

interface NavItem {
  label: string;
  route: string;
  icon: string;
  roles: string[];
  badge?: string;
}

interface NavSection {
  title: string;
  roles: string[];
  items: NavItem[];
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

  private readonly allSections: NavSection[] = [
    {
      title: 'Main Menu',
      roles: ['ADMIN', 'CORPORATE', 'INDIVIDUAL'],
      items: [
        { label: 'Dashboard', route: '/dashboard', icon: '📊', roles: ['ADMIN', 'CORPORATE'] },
        { label: 'AI Assistant', route: '/ai-assistant', icon: '🤖', roles: ['ADMIN', 'CORPORATE', 'INDIVIDUAL'], badge: 'New' },
        { label: 'Analytics', route: '/analytics', icon: '📈', roles: ['ADMIN', 'CORPORATE'] },
        { label: 'Products', route: '/products', icon: '📦', roles: ['ADMIN', 'CORPORATE', 'INDIVIDUAL'] },
        { label: 'Cart', route: '/cart', icon: '🛒', roles: ['INDIVIDUAL'] },
        { label: 'Orders', route: '/orders', icon: '📋', roles: ['ADMIN', 'CORPORATE', 'INDIVIDUAL'] },
      ],
    },
    {
      title: 'Management',
      roles: ['ADMIN', 'CORPORATE'],
      items: [
        { label: 'Customers', route: '/customers', icon: '👥', roles: ['ADMIN'] },
        { label: 'Store Settings', route: '/store-settings', icon: '🏪', roles: ['ADMIN', 'CORPORATE'] },
        { label: 'Shipments', route: '/shipments', icon: '🚚', roles: ['ADMIN', 'CORPORATE'] },
        { label: 'Reviews', route: '/reviews', icon: '⭐', roles: ['ADMIN', 'CORPORATE'] },
        { label: 'User Management', route: '/user-management', icon: '🔧', roles: ['ADMIN'] },
      ],
    },
  ];

  readonly sections = computed(() => {
    const role = this.auth.userRole();
    if (!role) return [];
    return this.allSections
      .filter(section => section.roles.includes(role))
      .map(section => ({
        ...section,
        items: section.items.filter(item => item.roles.includes(role)),
      }))
      .filter(section => section.items.length > 0);
  });

  toggle() {
    this.collapsed.update(v => !v);
  }
}
