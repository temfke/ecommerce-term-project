import { Component, ChangeDetectionStrategy, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Auth } from '../../../core/services/auth';

@Component({
  selector: 'app-header',
  imports: [RouterLink],
  templateUrl: './header.html',
  styleUrl: './header.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Header {
  private readonly auth = inject(Auth);

  readonly user = computed(() => this.auth.currentUser());
  readonly initials = computed(() => {
    const u = this.user();
    if (!u) return '?';
    return `${u.firstName.charAt(0)}${u.lastName.charAt(0)}`.toUpperCase();
  });
  readonly displayName = computed(() => {
    const u = this.user();
    if (!u) return '';
    return `${u.firstName} ${u.lastName}`;
  });
  readonly roleBadge = computed(() => {
    const u = this.user();
    if (!u) return '';
    return u.role.charAt(0) + u.role.slice(1).toLowerCase();
  });

  logout() {
    this.auth.logout();
  }
}
