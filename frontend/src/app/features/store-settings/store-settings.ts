import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { Store } from '../../core/models/store.model';

const STATUSES = ['PENDING_APPROVAL', 'OPEN', 'SUSPENDED', 'CLOSED'] as const;

@Component({
  selector: 'app-store-settings',
  imports: [DatePipe, ReactiveFormsModule],
  templateUrl: './store-settings.html',
  styleUrl: './store-settings.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StoreSettings implements OnInit {
  private readonly api = inject(Api);
  private readonly auth = inject(Auth);
  private readonly fb = inject(FormBuilder);

  readonly stores = signal<Store[]>([]);
  readonly loading = signal(true);
  readonly showForm = signal(false);
  readonly editingId = signal<number | null>(null);
  readonly error = signal('');
  readonly success = signal('');
  readonly statusUpdatingId = signal<number | null>(null);

  readonly isAdmin = computed(() => this.auth.userRole() === 'ADMIN');
  readonly statuses = STATUSES;

  readonly form = this.fb.nonNullable.group({
    name: ['', Validators.required],
    description: [''],
    logoUrl: [''],
  });

  ngOnInit() {
    this.loadStores();
  }

  loadStores() {
    this.loading.set(true);
    const obs = this.isAdmin() ? this.api.getStores() : this.api.getMyStores();
    obs.subscribe({
      next: (data) => { this.stores.set(data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  updateStatus(store: Store, status: string) {
    if (!this.isAdmin() || status === store.status) return;
    this.statusUpdatingId.set(store.id);
    this.error.set('');
    this.api.updateStoreStatus(store.id, status).subscribe({
      next: (updated) => {
        this.stores.update(list => list.map(s => s.id === updated.id ? updated : s));
        this.statusUpdatingId.set(null);
        this.success.set(`${updated.name} → ${updated.status}`);
      },
      error: (err) => {
        this.statusUpdatingId.set(null);
        this.error.set(err?.error?.message ?? 'Failed to update status.');
      },
    });
  }

  openCreate() {
    this.editingId.set(null);
    this.form.reset();
    this.showForm.set(true);
    this.error.set('');
    this.success.set('');
  }

  openEdit(store: Store) {
    this.editingId.set(store.id);
    this.form.patchValue({
      name: store.name,
      description: store.description,
      logoUrl: store.logoUrl ?? '',
    });
    this.showForm.set(true);
    this.error.set('');
    this.success.set('');
  }

  closeForm() {
    this.showForm.set(false);
    this.error.set('');
  }

  onSubmit() {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    const raw = this.form.getRawValue();
    const req = {
      name: raw.name,
      description: raw.description || undefined,
      logoUrl: raw.logoUrl || undefined,
    };
    const id = this.editingId();
    const obs = id ? this.api.updateStore(id, req) : this.api.createStore(req);
    obs.subscribe({
      next: () => {
        this.closeForm();
        this.success.set(id ? 'Store updated successfully.' : 'Store created successfully.');
        this.loadStores();
      },
      error: (err) => this.error.set(err.error?.message ?? 'Failed to save store'),
    });
  }

  statusClass(status: string): string {
    return status.toLowerCase().replace('_', '-');
  }
}
