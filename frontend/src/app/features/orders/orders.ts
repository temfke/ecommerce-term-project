import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DecimalPipe, DatePipe } from '@angular/common';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { Cart } from '../../core/services/cart';
import { Order, OrderStatus } from '../../core/models/order.model';

@Component({
  selector: 'app-orders',
  imports: [DecimalPipe, DatePipe],
  templateUrl: './orders.html',
  styleUrl: './orders.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Orders implements OnInit {
  private readonly api = inject(Api);
  private readonly auth = inject(Auth);
  readonly cart = inject(Cart);

  readonly orders = signal<Order[]>([]);
  readonly loading = signal(true);

  readonly isAdmin = computed(() => this.auth.userRole() === 'ADMIN');
  readonly isCorporate = computed(() => this.auth.userRole() === 'CORPORATE');
  readonly isIndividual = computed(() => this.auth.userRole() === 'INDIVIDUAL');

  readonly statuses: OrderStatus[] = ['PENDING', 'CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED'];

  ngOnInit() {
    this.loadOrders();
  }

  loadOrders() {
    this.loading.set(true);
    this.api.getMyOrders().subscribe({
      next: (data) => { this.orders.set(data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  updateStatus(id: number, status: string) {
    this.api.updateOrderStatus(id, status).subscribe(() => this.loadOrders());
  }

  statusClass(status: string): string {
    return status.toLowerCase().replace('_', '-');
  }

  formatPayment(m: string): string {
    return m.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  changeCartQty(productId: number, delta: number) {
    const item = this.cart.items().find(i => i.productId === productId);
    if (!item) return;
    this.cart.setQuantity(productId, item.quantity + delta);
  }

  removeFromCart(productId: number) {
    this.cart.remove(productId);
  }

  clearCart() {
    this.cart.clear();
  }
}
