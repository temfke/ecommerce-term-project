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
  readonly displayLimit = signal(PAGE_SIZE);

  readonly visibleUsers = computed(() => this.users().slice(0, this.displayLimit()));
  readonly hasMore = computed(() => this.displayLimit() < this.users().length);

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
    this.displayLimit.update(n => Math.min(n + PAGE_SIZE, this.users().length));
  }
}
