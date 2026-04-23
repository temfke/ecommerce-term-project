import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { User } from '../../core/models/user.model';
import { Address } from '../../core/models/address.model';
import { LOCATIONS, LocationCity, LocationCountry } from '../../core/data/locations';

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

  readonly addresses = signal<Address[]>([]);
  readonly addressesLoading = signal(true);
  readonly addressFormOpen = signal(false);
  readonly editingAddressId = signal<number | null>(null);
  readonly addressSaving = signal(false);
  readonly addressError = signal('');
  readonly addressSuccess = signal('');

  readonly verifySubmitting = signal(false);
  readonly verifyError = signal('');
  readonly verifySuccess = signal('');
  readonly verifyToken = signal('');

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

  readonly addressForm = this.fb.nonNullable.group({
    label: ['', [Validators.required, Validators.maxLength(60)]],
    line1: ['', [Validators.required, Validators.maxLength(200)]],
    line2: ['', Validators.maxLength(200)],
    city: ['', [Validators.required, Validators.maxLength(100)]],
    state: ['', Validators.maxLength(100)],
    postalCode: ['', [Validators.required, Validators.maxLength(30)]],
    country: ['', [Validators.required, Validators.maxLength(100)]],
    isDefault: [false],
  });

  readonly countries = LOCATIONS;
  readonly OTHER = '__other__';

  readonly countrySelection = signal<string>('');
  readonly citySelection = signal<string>('');
  readonly regionSelection = signal<string>('');

  readonly availableCities = computed<LocationCity[]>(() => {
    const country = this.countries.find(c => c.name === this.countrySelection());
    return country?.cities ?? [];
  });

  readonly availableRegions = computed<string[]>(() => {
    const city = this.availableCities().find(c => c.name === this.citySelection());
    return city?.regions ?? [];
  });

  readonly countryIsOther = computed(() => this.countrySelection() === this.OTHER);
  readonly cityIsOther = computed(() => this.citySelection() === this.OTHER);
  readonly regionIsOther = computed(() => this.regionSelection() === this.OTHER);

  ngOnInit() {
    this.api.getCurrentUser().subscribe({
      next: (user) => {
        this.user.set(user);
        this.populateForm(user);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
    this.loadAddresses();
  }

  private loadAddresses() {
    this.addressesLoading.set(true);
    this.api.getMyAddresses().subscribe({
      next: (list) => {
        this.addresses.set(list);
        this.addressesLoading.set(false);
      },
      error: () => {
        this.addresses.set([]);
        this.addressesLoading.set(false);
      },
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

    const values = this.form.getRawValue();
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

  openAddressForm(address?: Address) {
    this.addressError.set('');
    this.addressSuccess.set('');
    if (address) {
      this.editingAddressId.set(address.id);
      this.addressForm.patchValue({
        label: address.label,
        line1: address.line1,
        line2: address.line2 ?? '',
        city: address.city,
        state: address.state ?? '',
        postalCode: address.postalCode,
        country: address.country,
        isDefault: address.isDefault,
      });
      this.syncSelectionsFromForm(address.country, address.city, address.state ?? '');
    } else {
      this.editingAddressId.set(null);
      this.addressForm.reset({
        label: '', line1: '', line2: '', city: '', state: '',
        postalCode: '', country: '', isDefault: this.addresses().length === 0,
      });
      this.countrySelection.set('');
      this.citySelection.set('');
      this.regionSelection.set('');
    }
    this.addressFormOpen.set(true);
  }

  private syncSelectionsFromForm(country: string, city: string, region: string) {
    const matchedCountry = this.countries.find(c => c.name === country);
    if (matchedCountry) {
      this.countrySelection.set(matchedCountry.name);
      const matchedCity = matchedCountry.cities.find(ci => ci.name === city);
      if (matchedCity) {
        this.citySelection.set(matchedCity.name);
        const matchedRegion = matchedCity.regions.find(r => r === region);
        this.regionSelection.set(matchedRegion ?? (region ? this.OTHER : ''));
      } else {
        this.citySelection.set(city ? this.OTHER : '');
        this.regionSelection.set(region ? this.OTHER : '');
      }
    } else {
      this.countrySelection.set(country ? this.OTHER : '');
      this.citySelection.set(city ? this.OTHER : '');
      this.regionSelection.set(region ? this.OTHER : '');
    }
  }

  onCountrySelect(value: string) {
    this.countrySelection.set(value);
    this.citySelection.set('');
    this.regionSelection.set('');
    if (value === this.OTHER) {
      this.addressForm.patchValue({ country: '', city: '', state: '' });
    } else {
      this.addressForm.patchValue({ country: value, city: '', state: '' });
    }
  }

  onCitySelect(value: string) {
    this.citySelection.set(value);
    this.regionSelection.set('');
    if (value === this.OTHER) {
      this.addressForm.patchValue({ city: '', state: '' });
    } else {
      this.addressForm.patchValue({ city: value, state: '' });
    }
  }

  onRegionSelect(value: string) {
    this.regionSelection.set(value);
    if (value === this.OTHER) {
      this.addressForm.patchValue({ state: '' });
    } else {
      this.addressForm.patchValue({ state: value });
    }
  }

  closeAddressForm() {
    this.addressFormOpen.set(false);
    this.editingAddressId.set(null);
  }

  submitAddress() {
    if (this.addressForm.invalid) { this.addressForm.markAllAsTouched(); return; }
    this.addressSaving.set(true);
    this.addressError.set('');
    const values = this.addressForm.getRawValue();
    const payload = {
      label: values.label.trim(),
      line1: values.line1.trim(),
      line2: values.line2?.trim() || undefined,
      city: values.city.trim(),
      state: values.state?.trim() || undefined,
      postalCode: values.postalCode.trim(),
      country: values.country.trim(),
      isDefault: values.isDefault,
    };
    const editId = this.editingAddressId();
    const obs = editId != null
      ? this.api.updateAddress(editId, payload)
      : this.api.createAddress(payload);
    obs.subscribe({
      next: () => {
        this.addressSaving.set(false);
        this.addressSuccess.set(editId != null ? 'Address updated.' : 'Address added.');
        this.closeAddressForm();
        this.loadAddresses();
      },
      error: (err) => {
        this.addressSaving.set(false);
        this.addressError.set(err?.error?.message ?? 'Failed to save address.');
      },
    });
  }

  setDefaultAddress(id: number) {
    this.api.setDefaultAddress(id).subscribe({
      next: () => {
        this.addressSuccess.set('Default address updated.');
        this.loadAddresses();
      },
      error: (err) => this.addressError.set(err?.error?.message ?? 'Failed to set default.'),
    });
  }

  deleteAddress(id: number) {
    if (!confirm('Delete this address?')) return;
    this.api.deleteAddress(id).subscribe({
      next: () => {
        this.addressSuccess.set('Address deleted.');
        this.loadAddresses();
      },
      error: (err) => this.addressError.set(err?.error?.message ?? 'Failed to delete address.'),
    });
  }

  updateVerifyToken(value: string) {
    this.verifyToken.set(value);
  }

  submitVerification() {
    const token = this.verifyToken().trim();
    if (!token) { this.verifyError.set('Enter the verification token.'); return; }
    this.verifySubmitting.set(true);
    this.verifyError.set('');
    this.verifySuccess.set('');
    this.api.verifyEmail(token).subscribe({
      next: (res) => {
        this.verifySubmitting.set(false);
        this.verifySuccess.set('Email verified successfully.');
        this.verifyToken.set('');
        this.auth.updateStoredAuth(res);
        const u = this.user();
        if (u) this.user.set({ ...u, emailVerified: true });
      },
      error: (err) => {
        this.verifySubmitting.set(false);
        this.verifyError.set(err?.error?.message ?? 'Verification failed.');
      },
    });
  }

  resendVerification() {
    this.verifySubmitting.set(true);
    this.verifyError.set('');
    this.verifySuccess.set('');
    this.api.resendEmailVerification().subscribe({
      next: (res) => {
        this.verifySubmitting.set(false);
        if (res.emailVerificationToken) {
          this.verifyToken.set(res.emailVerificationToken);
          this.verifySuccess.set('New token issued — check the server log or use the value below to verify.');
        } else {
          this.verifySuccess.set('A new verification token has been sent.');
        }
        this.auth.updateStoredAuth(res);
      },
      error: (err) => {
        this.verifySubmitting.set(false);
        this.verifyError.set(err?.error?.message ?? 'Failed to resend token.');
      },
    });
  }

  logout() {
    this.auth.logout();
  }
}
