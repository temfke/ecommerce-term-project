import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { Review } from '../../core/models/review.model';

@Component({
  selector: 'app-reviews',
  imports: [DatePipe, ReactiveFormsModule],
  templateUrl: './reviews.html',
  styleUrl: './reviews.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Reviews implements OnInit {
  private readonly api = inject(Api);
  private readonly auth = inject(Auth);
  private readonly fb = inject(FormBuilder);

  readonly reviews = signal<Review[]>([]);
  readonly loading = signal(true);
  readonly showForm = signal(false);
  readonly error = signal('');

  readonly isIndividual = computed(() => this.auth.userRole() === 'INDIVIDUAL');
  readonly isAdmin = computed(() => this.auth.userRole() === 'ADMIN');

  readonly form = this.fb.nonNullable.group({
    productId: [0, [Validators.required, Validators.min(1)]],
    starRating: [5, [Validators.required, Validators.min(1), Validators.max(5)]],
    reviewBody: [''],
  });

  ngOnInit() {
    this.loadReviews();
  }

  loadReviews() {
    this.loading.set(true);
    this.api.getMyReviews().subscribe({
      next: (data) => { this.reviews.set(data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  openCreate() {
    this.form.reset({ starRating: 5, productId: 0 });
    this.showForm.set(true);
    this.error.set('');
  }

  closeForm() {
    this.showForm.set(false);
    this.error.set('');
  }

  onSubmit() {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    this.api.createReview(this.form.getRawValue()).subscribe({
      next: () => { this.closeForm(); this.loadReviews(); },
      error: (err) => this.error.set(err.error?.message ?? 'Failed to submit review'),
    });
  }

  deleteReview(id: number) {
    this.api.deleteReview(id).subscribe(() => this.loadReviews());
  }

  starsDisplay(rating: number): string {
    return '★'.repeat(rating) + '☆'.repeat(5 - rating);
  }
}
