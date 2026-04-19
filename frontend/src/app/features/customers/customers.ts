import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Api } from '../../core/services/api';
import { User } from '../../core/models/user.model';

@Component({
  selector: 'app-customers',
  imports: [DatePipe],
  templateUrl: './customers.html',
  styleUrl: './customers.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Customers implements OnInit {
  private readonly api = inject(Api);

  readonly users = signal<User[]>([]);
  readonly loading = signal(true);
  readonly filterRole = signal('');

  ngOnInit() {
    this.loadUsers();
  }

  loadUsers() {
    this.loading.set(true);
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
}
