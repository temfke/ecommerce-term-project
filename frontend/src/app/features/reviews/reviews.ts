import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { Review } from '../../core/models/review.model';
import { InfiniteScrollDirective } from '../../shared/directives/infinite-scroll.directive';

const INITIAL_PAGE_SIZE = 200;
const NEXT_PAGE_SIZE = 100;

@Component({
  selector: 'app-reviews',
  imports: [DatePipe, RouterLink, InfiniteScrollDirective],
  templateUrl: './reviews.html',
  styleUrl: './reviews.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Reviews implements OnInit {
  private readonly api = inject(Api);
  private readonly auth = inject(Auth);

  readonly reviews = signal<Review[]>([]);
  readonly loading = signal(true);
  readonly loadingMore = signal(false);
  readonly endReached = signal(false);
  readonly expandedIds = signal<ReadonlySet<number>>(new Set());

  readonly CLAMP_THRESHOLD = 280;

  readonly visibleReviews = computed(() => this.reviews());
  readonly hasMore = computed(() => !this.endReached());

  readonly isIndividual = computed(() => this.auth.userRole() === 'INDIVIDUAL');
  readonly isAdmin = computed(() => this.auth.userRole() === 'ADMIN');
  readonly currentUserId = computed(() => this.auth.currentUser()?.userId ?? null);

  readonly errorMessage = signal('');

  isOwnReview(review: Review): boolean {
    const uid = this.currentUserId();
    return uid != null && review.userId === uid;
  }

  canDelete(review: Review): boolean {
    return this.isAdmin() || this.isOwnReview(review);
  }

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

  deleteReview(review: Review) {
    if (!this.canDelete(review)) return;
    const prompt = this.isOwnReview(review)
      ? 'Delete your review? This cannot be undone.'
      : `Delete this review by ${review.userName}? This cannot be undone.`;
    if (!confirm(prompt)) return;
    this.errorMessage.set('');
    this.api.deleteReview(review.id).subscribe({
      next: () => {
        this.reviews.update(list => list.filter(r => r.id !== review.id));
      },
      error: (err) => {
        this.errorMessage.set(err?.error?.message ?? 'Failed to delete review.');
      },
    });
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
