import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Api } from '../../core/services/api';
import { Shipment, ShipmentStatus } from '../../core/models/shipment.model';

@Component({
  selector: 'app-shipments',
  imports: [DatePipe],
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

  ngOnInit() {
    this.loadShipments();
  }

  loadShipments() {
    this.loading.set(true);
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
}
