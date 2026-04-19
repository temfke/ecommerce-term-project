import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { DashboardStats } from '../../core/models/dashboard.model';
import { Store } from '../../core/models/store.model';

@Component({
  selector: 'app-analytics',
  imports: [DecimalPipe],
  templateUrl: './analytics.html',
  styleUrl: './analytics.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Analytics implements OnInit {
  private readonly api = inject(Api);
  private readonly auth = inject(Auth);

  readonly stats = signal<DashboardStats | null>(null);
  readonly stores = signal<Store[]>([]);
  readonly selectedStoreId = signal<number | null>(null);
  readonly loading = signal(true);

  readonly isAdmin = this.auth.userRole() === 'ADMIN';

  ngOnInit() {
    if (this.isAdmin) {
      this.loadAdminAnalytics();
    } else {
      this.api.getMyStores().subscribe(s => {
        this.stores.set(s);
        if (s.length > 0) this.selectStore(s[0].id);
        else this.loading.set(false);
      });
    }
  }

  private loadAdminAnalytics() {
    this.api.getAdminDashboard().subscribe({
      next: (data) => { this.stats.set(data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  selectStore(storeId: number) {
    this.selectedStoreId.set(storeId);
    this.loading.set(true);
    this.api.getCorporateDashboard(storeId).subscribe({
      next: (data) => { this.stats.set(data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  revenuePerOrder(): number {
    const s = this.stats();
    if (!s || s.totalOrders === 0) return 0;
    return s.totalRevenue / s.totalOrders;
  }

  fulfillmentRate(): number {
    const s = this.stats();
    if (!s || s.totalOrders === 0) return 0;
    return (s.deliveredOrders / s.totalOrders) * 100;
  }
}
