import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Api } from '../../core/services/api';
import { User } from '../../core/models/user.model';
import { InfiniteScrollDirective } from '../../shared/directives/infinite-scroll.directive';

const PAGE_SIZE = 200;

@Component({
  selector: 'app-customers',
  imports: [DatePipe, InfiniteScrollDirective],
  templateUrl: './customers.html',
  styleUrl: './customers.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Customers implements OnInit {
  private readonly api = inject(Api);

  readonly users = signal<User[]>([]);
  readonly loading = signal(true);
  readonly filterRole = signal('');
  readonly searchQuery = signal('');
  readonly displayLimit = signal(PAGE_SIZE);
  readonly deletingId = signal<number | null>(null);
  readonly actionError = signal('');

  readonly filteredUsers = computed(() => {
    const q = this.searchQuery().trim().toLowerCase();
    if (!q) return this.users();
    return this.users().filter(u => {
      const name = `${u.firstName} ${u.lastName}`.toLowerCase();
      return name.includes(q)
        || u.email.toLowerCase().includes(q)
        || (u.phone ?? '').toLowerCase().includes(q);
    });
  });

  readonly visibleUsers = computed(() => this.filteredUsers().slice(0, this.displayLimit()));
  readonly hasMore = computed(() => this.displayLimit() < this.filteredUsers().length);

  ngOnInit() {
    this.loadUsers();
  }

  loadUsers() {
    this.loading.set(true);
    this.displayLimit.set(PAGE_SIZE);
    const role = this.filterRole() || undefined;
    this.api.getUsers(role).subscribe({
      next: (data) => { this.users.set(data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  onFilterChange(role: string) {
    this.filterRole.set(role);
    this.loadUsers();
  }

  loadMore() {
    if (!this.hasMore()) return;
    this.displayLimit.update(n => Math.min(n + PAGE_SIZE, this.filteredUsers().length));
  }

  onSearch(value: string) {
    this.searchQuery.set(value);
    this.displayLimit.set(PAGE_SIZE);
  }

  deleteUser(user: User) {
    if (this.deletingId() != null) return;
    if (!confirm(`Delete ${user.firstName} ${user.lastName} (${user.email})? This cannot be undone.`)) return;
    this.deletingId.set(user.id);
    this.actionError.set('');
    this.api.deleteUser(user.id).subscribe({
      next: () => {
        this.users.update(list => list.filter(u => u.id !== user.id));
        this.deletingId.set(null);
      },
      error: (err) => {
        this.deletingId.set(null);
        this.actionError.set(err?.error?.message ?? `Failed to delete ${user.email}.`);
      },
    });
  }
}
