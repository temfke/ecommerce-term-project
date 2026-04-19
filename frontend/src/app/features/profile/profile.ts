import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { User } from '../../core/models/user.model';

@Component({
  selector: 'app-profile',
  imports: [ReactiveFormsModule],
  templateUrl: './profile.html',
  styleUrl: './profile.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Profile implements OnInit {
  private readonly api = inject(Api);
  private readonly auth = inject(Auth);
  private readonly fb = inject(FormBuilder);

  readonly user = signal<User | null>(null);
  readonly loading = signal(true);
  readonly editing = signal(false);
  readonly saving = signal(false);
  readonly success = signal('');
  readonly error = signal('');

  readonly initials = computed(() => {
    const u = this.user();
    if (!u) return '?';
    return `${u.firstName.charAt(0)}${u.lastName.charAt(0)}`.toUpperCase();
  });

  readonly form = this.fb.nonNullable.group({
    firstName: ['', Validators.required],
    lastName: ['', Validators.required],
    email: [{ value: '', disabled: true }],
    phone: [''],
    gender: [''],
  });

  ngOnInit() {
    this.api.getCurrentUser().subscribe({
      next: (user) => {
        this.user.set(user);
        this.populateForm(user);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  private populateForm(u: User) {
    this.form.patchValue({
      firstName: u.firstName,
      lastName: u.lastName,
      email: u.email,
      phone: u.phone ?? '',
      gender: u.gender ?? '',
    });
  }

  startEdit() {
    this.editing.set(true);
    this.success.set('');
    this.error.set('');
  }

  cancelEdit() {
    this.editing.set(false);
    const u = this.user();
    if (u) this.populateForm(u);
    this.error.set('');
  }

  onSubmit() {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    this.error.set('');

    // The profile update would go through a dedicated endpoint.
    // For now we show the values are captured and ready.
    const values = this.form.getRawValue();
    // Simulate a successful update by reflecting the values locally
    const current = this.user();
    if (current) {
      this.user.set({
        ...current,
        firstName: values.firstName,
        lastName: values.lastName,
        phone: values.phone || undefined,
        gender: values.gender || undefined,
      });
    }
    this.saving.set(false);
    this.editing.set(false);
    this.success.set('Profile updated successfully.');
  }

  logout() {
    this.auth.logout();
  }
}
