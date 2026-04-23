import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DecimalPipe, DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { Cart } from '../../core/services/cart';
import { Order, OrderStatus } from '../../core/models/order.model';
import { Address } from '../../core/models/address.model';
import { InfiniteScrollDirective } from '../../shared/directives/infinite-scroll.directive';

const PAGE_SIZE = 200;

@Component({
  selector: 'app-orders',
  imports: [DecimalPipe, DatePipe, RouterLink, InfiniteScrollDirective],
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
  readonly view = signal<'cart' | 'orders'>('orders');
  readonly displayLimit = signal(PAGE_SIZE);

  readonly visibleOrders = computed(() => this.orders().slice(0, this.displayLimit()));
  readonly hasMore = computed(() => this.displayLimit() < this.orders().length);

  readonly isAdmin = computed(() => this.auth.userRole() === 'ADMIN');
  readonly isCorporate = computed(() => this.auth.userRole() === 'CORPORATE');
  readonly isIndividual = computed(() => this.auth.userRole() === 'INDIVIDUAL');
  readonly showCart = computed(() => this.view() === 'cart' && this.isIndividual());
  readonly showOrders = computed(() => this.view() === 'orders');
  readonly pageTitle = computed(() => this.showCart() ? 'Cart' : 'Orders');

  readonly statuses: OrderStatus[] = ['PENDING', 'CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED', 'CANCELLED', 'RETURNED'];

  readonly shippingAddress = signal('');
  readonly addresses = signal<Address[]>([]);
  readonly selectedAddressId = signal<number | 'manual'>('manual');
  readonly paymentLoading = signal(false);
  readonly paymentError = signal('');
  readonly paymentSuccess = signal('');

  readonly distinctStoreCount = computed(() => {
    const ids = new Set(this.cart.items().map(i => i.storeId));
    return ids.size;
  });

  ngOnInit() {
    const routeView = this.route.snapshot.data['view'];
    if (routeView === 'cart' && this.isIndividual()) {
      this.view.set('cart');
    } else {
      this.view.set('orders');
    }
    this.loadOrders();
    if (this.isIndividual()) {
      this.loadAddresses();
    }
    this.handleStripeRedirect();
  }

  loadAddresses() {
    this.api.getMyAddresses().subscribe({
      next: (data) => {
        this.addresses.set(data);
        const def = data.find(a => a.isDefault) ?? data[0];
        if (def) {
          this.selectedAddressId.set(def.id);
          this.shippingAddress.set(this.formatAddress(def));
        }
      },
      error: () => this.addresses.set([]),
    });
  }

  formatAddress(a: Address): string {
    const parts = [
      a.line1,
      a.line2 || '',
      [a.city, a.state, a.postalCode].filter(Boolean).join(', '),
      a.country,
    ].filter(p => p && p.trim().length > 0);
    return parts.join('\n');
  }

  onAddressSelect(value: string) {
    if (value === 'manual') {
      this.selectedAddressId.set('manual');
      this.shippingAddress.set('');
      return;
    }
    const id = Number(value);
    const addr = this.addresses().find(a => a.id === id);
    if (addr) {
      this.selectedAddressId.set(id);
      this.shippingAddress.set(this.formatAddress(addr));
    }
  }

  loadOrders() {
    if (!this.showOrders()) {
      this.loading.set(false);
      return;
    }
    this.loading.set(true);
    this.displayLimit.set(PAGE_SIZE);
    const obs = this.isIndividual() ? this.api.getMyOrders() : this.api.getOrders();
    obs.subscribe({
      next: (data) => { this.orders.set(data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  loadMoreOrders() {
    if (!this.hasMore()) return;
    this.displayLimit.update(n => Math.min(n + PAGE_SIZE, this.orders().length));
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
    this.selectedAddressId.set('manual');
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
