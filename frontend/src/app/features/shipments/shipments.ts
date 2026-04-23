import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Api } from '../../core/services/api';
import { Shipment, ShipmentStatus } from '../../core/models/shipment.model';
import { InfiniteScrollDirective } from '../../shared/directives/infinite-scroll.directive';

const PAGE_SIZE = 200;

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
  readonly filterStatus = signal('');
  readonly statuses: ShipmentStatus[] = ['PENDING', 'PROCESSING', 'IN_TRANSIT', 'DELIVERED', 'RETURNED'];
  readonly displayLimit = signal(PAGE_SIZE);

  readonly visibleShipments = computed(() => this.shipments().slice(0, this.displayLimit()));
  readonly hasMore = computed(() => this.displayLimit() < this.shipments().length);

  ngOnInit() {
    this.loadShipments();
  }

  loadShipments() {
    this.loading.set(true);
    this.displayLimit.set(PAGE_SIZE);
    const status = this.filterStatus() || undefined;
    this.api.getShipments(status).subscribe({
      next: (data) => { this.shipments.set(data); this.loading.set(false); },
      error: () => this.loading.set(false),
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
    if (!this.hasMore()) return;
    this.displayLimit.update(n => Math.min(n + PAGE_SIZE, this.shipments().length));
  }
}
