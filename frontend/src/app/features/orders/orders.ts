import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DecimalPipe, DatePipe } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
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
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly cart = inject(Cart);

  readonly orders = signal<Order[]>([]);
  readonly loading = signal(true);

  readonly isAdmin = computed(() => this.auth.userRole() === 'ADMIN');
  readonly isCorporate = computed(() => this.auth.userRole() === 'CORPORATE');
  readonly isIndividual = computed(() => this.auth.userRole() === 'INDIVIDUAL');

  readonly statuses: OrderStatus[] = ['PENDING', 'CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED'];

  readonly shippingAddress = signal('');
  readonly paymentLoading = signal(false);
  readonly paymentError = signal('');
  readonly paymentSuccess = signal('');

  readonly distinctStoreCount = computed(() => {
    const ids = new Set(this.cart.items().map(i => i.storeId));
    return ids.size;
  });

  ngOnInit() {
    this.loadOrders();
    this.handleStripeRedirect();
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

  updateShippingAddress(value: string) {
    this.shippingAddress.set(value);
  }

  payWithStripe() {
    const items = this.cart.items();
    if (items.length === 0 || this.paymentLoading()) return;
    if (this.distinctStoreCount() > 1) {
      this.paymentError.set('Please check out one store at a time. Remove items from other stores to continue.');
      return;
    }
    const storeId = items[0].storeId;
    this.paymentLoading.set(true);
    this.paymentError.set('');
    this.paymentSuccess.set('');
    this.api.createCheckoutSession({
      storeId,
      shippingAddress: this.shippingAddress().trim() || undefined,
      items: items.map(i => ({ productId: i.productId, quantity: i.quantity })),
    }).subscribe({
      next: (res) => { window.location.href = res.url; },
      error: (err) => {
        this.paymentLoading.set(false);
        this.paymentError.set(err?.error?.message ?? 'Could not start payment.');
      },
    });
  }

  private handleStripeRedirect() {
    const params = this.route.snapshot.queryParamMap;
    const sessionId = params.get('stripe_session_id');
    const status = params.get('stripe_status');
    if (!sessionId) return;

    if (status === 'cancel') {
      this.paymentError.set('Payment cancelled. Your cart is still saved.');
      this.router.navigate([], { queryParams: {}, replaceUrl: true });
      return;
    }

    if (status === 'success') {
      this.paymentLoading.set(true);
      this.api.confirmPayment(sessionId).subscribe({
        next: (res) => {
          this.paymentLoading.set(false);
          if (res.status === 'paid') {
            this.cart.clear();
            this.paymentSuccess.set(`Payment received! Order #${res.order?.id ?? ''} created.`);
            this.loadOrders();
          } else {
            this.paymentError.set(`Payment status: ${res.status}.`);
          }
          this.router.navigate([], { queryParams: {}, replaceUrl: true });
        },
        error: (err) => {
          this.paymentLoading.set(false);
          this.paymentError.set(err?.error?.message ?? 'Could not confirm payment.');
          this.router.navigate([], { queryParams: {}, replaceUrl: true });
        },
      });
    }
  }
}
