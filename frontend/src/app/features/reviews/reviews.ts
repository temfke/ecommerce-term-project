import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { Review } from '../../core/models/review.model';
import { InfiniteScrollDirective } from '../../shared/directives/infinite-scroll.directive';

const INITIAL_PAGE_SIZE = 200;
const NEXT_PAGE_SIZE = 100;

@Component({
  selector: 'app-reviews',
  imports: [DatePipe, ReactiveFormsModule, InfiniteScrollDirective],
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
  readonly loadingMore = signal(false);
  readonly endReached = signal(false);
  readonly showForm = signal(false);
  readonly error = signal('');
  readonly expandedIds = signal<ReadonlySet<number>>(new Set());

  readonly CLAMP_THRESHOLD = 280;

  readonly visibleReviews = computed(() => this.reviews());
  readonly hasMore = computed(() => !this.endReached());

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
    this.endReached.set(false);
    this.reviews.set([]);
    if (this.isIndividual()) {
      this.api.getMyReviews().subscribe({
        next: (data) => {
          this.reviews.set(data);
          this.endReached.set(true);
          this.loading.set(false);
        },
        error: () => { this.loading.set(false); this.endReached.set(true); },
      });
      return;
    }
    this.api.getReviews({ limit: INITIAL_PAGE_SIZE, offset: 0 }).subscribe({
      next: (data) => {
        this.reviews.set(data);
        if (data.length < INITIAL_PAGE_SIZE) this.endReached.set(true);
        this.loading.set(false);
      },
      error: () => { this.loading.set(false); this.endReached.set(true); },
    });
  }

  loadMore() {
    if (this.loadingMore() || this.endReached() || this.loading() || this.isIndividual()) return;
    this.loadingMore.set(true);
    const offset = this.reviews().length;
    this.api.getReviews({ limit: NEXT_PAGE_SIZE, offset }).subscribe({
      next: (data) => {
        this.reviews.update(curr => [...curr, ...data]);
        if (data.length < NEXT_PAGE_SIZE) this.endReached.set(true);
        this.loadingMore.set(false);
      },
      error: () => { this.loadingMore.set(false); this.endReached.set(true); },
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

  isExpanded(id: number): boolean {
    return this.expandedIds().has(id);
  }

  isLong(body: string | null | undefined): boolean {
    return !!body && body.length > this.CLAMP_THRESHOLD;
  }

  toggleExpanded(id: number) {
    this.expandedIds.update(curr => {
      const next = new Set(curr);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
}
