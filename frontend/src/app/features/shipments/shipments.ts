import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Api } from '../../core/services/api';
import { Shipment, ShipmentStatus } from '../../core/models/shipment.model';
import { InfiniteScrollDirective } from '../../shared/directives/infinite-scroll.directive';

const INITIAL_PAGE_SIZE = 200;
const NEXT_PAGE_SIZE = 100;

@Component({
  selector: 'app-shipments',
  imports: [DatePipe, InfiniteScrollDirective],
  templateUrl: './shipments.html',
  styleUrl: './shipments.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Shipments implements OnInit {
  private readonly api = inject(Api);

  readonly shipments = signal<Shipment[]>([]);
  readonly loading = signal(true);
  readonly loadingMore = signal(false);
  readonly endReached = signal(false);
  readonly filterStatus = signal('');
  readonly statuses: ShipmentStatus[] = ['PENDING', 'PROCESSING', 'IN_TRANSIT', 'DELIVERED', 'RETURNED'];

  readonly visibleShipments = computed(() => this.shipments());
  readonly hasMore = computed(() => !this.endReached());

  ngOnInit() {
    this.loadShipments();
  }

  loadShipments() {
    this.loading.set(true);
    this.endReached.set(false);
    this.shipments.set([]);
    const status = this.filterStatus() || undefined;
    this.api.getShipments(status, { limit: INITIAL_PAGE_SIZE, offset: 0 }).subscribe({
      next: (data) => {
        this.shipments.set(data);
        if (data.length < INITIAL_PAGE_SIZE) this.endReached.set(true);
        this.loading.set(false);
      },
      error: () => { this.loading.set(false); this.endReached.set(true); },
    });
  }

  onFilterChange(status: string) {
    this.filterStatus.set(status);
    this.loadShipments();
  }

  updateStatus(id: number, status: string) {
    this.api.updateShipmentStatus(id, status).subscribe(() => this.loadShipments());
  }

  statusClass(status: string): string {
    return status.toLowerCase().replace('_', '-');
  }

  loadMore() {
    if (this.loadingMore() || this.endReached() || this.loading()) return;
    this.loadingMore.set(true);
    const status = this.filterStatus() || undefined;
    const offset = this.shipments().length;
    this.api.getShipments(status, { limit: NEXT_PAGE_SIZE, offset }).subscribe({
      next: (data) => {
        this.shipments.update(curr => [...curr, ...data]);
        if (data.length < NEXT_PAGE_SIZE) this.endReached.set(true);
        this.loadingMore.set(false);
      },
      error: () => { this.loadingMore.set(false); this.endReached.set(true); },
    });
  }
}
