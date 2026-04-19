import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { DashboardStats } from '../../core/models/dashboard.model';
import { Store } from '../../core/models/store.model';

@Component({
  selector: 'app-dashboard',
  imports: [DecimalPipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Dashboard implements OnInit {
  private readonly api = inject(Api);
  private readonly auth = inject(Auth);

  readonly stats = signal<DashboardStats | null>(null);
  readonly stores = signal<Store[]>([]);
  readonly selectedStoreId = signal<number | null>(null);
  readonly loading = signal(true);

  ngOnInit() {
    const role = this.auth.userRole();
    if (role === 'ADMIN') {
      this.loadAdminDashboard();
    } else if (role === 'CORPORATE') {
      this.loadCorporateStores();
    } else {
      this.loadAdminDashboard();
    }
  }

  private loadAdminDashboard() {
    this.api.getAdminDashboard().subscribe({
      next: (data) => {
        this.stats.set(data);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  private loadCorporateStores() {
    this.api.getMyStores().subscribe({
      next: (stores) => {
        this.stores.set(stores);
        if (stores.length > 0) {
          this.selectStore(stores[0].id);
        } else {
          this.loading.set(false);
        }
      },
      error: () => this.loading.set(false),
    });
  }

  selectStore(storeId: number) {
    this.selectedStoreId.set(storeId);
    this.loading.set(true);
    this.api.getCorporateDashboard(storeId).subscribe({
      next: (data) => {
        this.stats.set(data);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
