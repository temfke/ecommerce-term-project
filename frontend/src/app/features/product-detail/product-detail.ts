import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DecimalPipe, DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { Cart } from '../../core/services/cart';
import { Product } from '../../core/models/product.model';
import { Review, ReviewVoteType } from '../../core/models/review.model';

@Component({
  selector: 'app-product-detail',
  imports: [DecimalPipe, DatePipe, RouterLink],
  templateUrl: './product-detail.html',
  styleUrl: './product-detail.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProductDetail implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly api = inject(Api);
  private readonly auth = inject(Auth);
  readonly cart = inject(Cart);

  readonly product = signal<Product | null>(null);
  readonly reviews = signal<Review[]>([]);
  readonly summary = signal<{ count: number; averageRating: number }>({ count: 0, averageRating: 0 });
  readonly loading = signal(true);
  readonly reviewsLoading = signal(true);
  readonly notFound = signal(false);
  readonly detailQty = signal(1);
  readonly addedFlash = signal(false);
  readonly votingId = signal<number | null>(null);
  readonly voteError = signal('');

  readonly formRating = signal(0);
  readonly formHoverRating = signal(0);
  readonly formBody = signal('');
  readonly submitting = signal(false);
  readonly submitError = signal('');
  readonly submitSuccess = signal(false);

  readonly currentUserId = computed(() => this.auth.currentUser()?.userId ?? null);
  readonly canReview = computed(() => this.auth.isAuthenticated());

  readonly maxAddable = computed(() => {
    const p = this.product();
    if (!p) return 0;
    return Math.max(0, p.stockQuantity - this.cart.quantityOf(p.id));
  });

  readonly myReviews = computed(() => {
    const uid = this.currentUserId();
    if (uid == null) return [] as Review[];
    return this.reviews().filter(r => r.userId === uid);
  });

  readonly otherReviews = computed(() => {
    const uid = this.currentUserId();
    if (uid == null) return this.reviews();
    return this.reviews().filter(r => r.userId !== uid);
  });

  readonly ratingBreakdown = computed(() => {
    const stars = [5, 4, 3, 2, 1];
    const reviews = this.reviews();
    if (reviews.length === 0) return stars.map(s => ({ stars: s, count: 0, pct: 0 }));
    return stars.map(s => {
      const count = reviews.filter(r => r.starRating === s).length;
      return { stars: s, count, pct: Math.round((count / reviews.length) * 100) };
    });
  });

  ngOnInit() {
    this.route.paramMap.subscribe(params => {
      const idRaw = params.get('id');
      const id = idRaw ? Number(idRaw) : NaN;
      if (!Number.isFinite(id)) {
        this.notFound.set(true);
        this.loading.set(false);
        return;
      }
      this.load(id);
    });
  }

  private load(id: number) {
    this.loading.set(true);
    this.reviewsLoading.set(true);
    this.notFound.set(false);
    this.detailQty.set(1);
    this.resetReviewForm();

    this.api.getProduct(id).subscribe({
      next: (p) => {
        this.product.set(p);
        this.loading.set(false);
      },
      error: () => {
        this.notFound.set(true);
        this.loading.set(false);
      },
    });

    this.reloadReviews(id);
  }

  private reloadReviews(id: number) {
    this.api.getProductRatingSummary(id).subscribe({
      next: (s) => this.summary.set(s),
      error: () => this.summary.set({ count: 0, averageRating: 0 }),
    });

    if (this.auth.isAuthenticated()) {
      forkJoin({
        recent: this.api.getReviewsByProduct(id).pipe(catchError(() => of([] as Review[]))),
        mine: this.api.getMyReviewsForProduct(id).pipe(catchError(() => of([] as Review[]))),
      }).subscribe({
        next: ({ recent, mine }) => {
          this.reviews.set(this.mergeReviews(recent, mine));
          this.reviewsLoading.set(false);
        },
        error: () => this.reviewsLoading.set(false),
      });
    } else {
      this.api.getReviewsByProduct(id).subscribe({
        next: (r) => {
          this.reviews.set(r);
          this.reviewsLoading.set(false);
        },
        error: () => this.reviewsLoading.set(false),
      });
    }
  }

  private mergeReviews(recent: Review[], mine: Review[]): Review[] {
    const seen = new Set(recent.map(r => r.id));
    const merged = [...recent];
    for (const r of mine) {
      if (!seen.has(r.id)) merged.push(r);
    }
    return merged;
  }

  changeDetailQty(delta: number) {
    const max = this.maxAddable();
    if (max <= 0) { this.detailQty.set(0); return; }
    this.detailQty.update(q => Math.max(1, Math.min(max, q + delta)));
  }

  addToCart() {
    const p = this.product();
    if (!p || this.maxAddable() <= 0) return;
    this.cart.add(p, this.detailQty());
    this.addedFlash.set(true);
    setTimeout(() => this.addedFlash.set(false), 1500);
  }

  goBack() {
    this.router.navigate(['/products']);
  }

  starArray(rating: number): boolean[] {
    const filled = Math.round(rating);
    return Array.from({ length: 5 }, (_, i) => i < filled);
  }

  setFormRating(rating: number) {
    this.formRating.set(rating);
    this.submitError.set('');
  }

  setFormHover(rating: number) {
    this.formHoverRating.set(rating);
  }

  updateFormBody(value: string) {
    this.formBody.set(value);
  }

  isMyReview(r: Review): boolean {
    const uid = this.currentUserId();
    return uid != null && r.userId === uid;
  }

  vote(review: Review, type: ReviewVoteType) {
    if (!this.auth.isAuthenticated()) {
      this.voteError.set('Please log in to vote on reviews.');
      return;
    }
    if (this.isMyReview(review)) {
      this.voteError.set('You cannot vote on your own review.');
      return;
    }
    if (this.votingId() === review.id) return;

    this.votingId.set(review.id);
    this.voteError.set('');
    this.api.voteOnReview(review.id, type).subscribe({
      next: (updated) => {
        this.reviews.update(list => list.map(r => r.id === updated.id ? { ...r, ...updated } : r));
        this.votingId.set(null);
      },
      error: (err) => {
        this.votingId.set(null);
        this.voteError.set(err?.error?.message ?? 'Failed to record vote.');
      },
    });
  }

  submitReview() {
    const p = this.product();
    if (!p || this.submitting()) return;
    const rating = this.formRating();
    if (rating < 1 || rating > 5) {
      this.submitError.set('Please select a star rating.');
      return;
    }
    this.submitting.set(true);
    this.submitError.set('');
    const body = this.formBody().trim();
    this.api.createReview({
      productId: p.id,
      starRating: rating,
      reviewBody: body || undefined,
    }).subscribe({
      next: (created) => {
        this.submitting.set(false);
        this.submitSuccess.set(true);
        this.resetReviewForm();
        this.reviews.update(list => [created, ...list.filter(r => r.id !== created.id)]);
        this.summary.update(s => ({
          count: s.count + 1,
          averageRating: Math.round(((s.averageRating * s.count + created.starRating) / (s.count + 1)) * 10) / 10,
        }));
        this.reloadReviews(p.id);
        setTimeout(() => this.submitSuccess.set(false), 2500);
      },
      error: (err) => {
        this.submitting.set(false);
        this.submitError.set(err?.error?.message ?? 'Failed to submit review.');
      },
    });
  }

  private resetReviewForm() {
    this.formRating.set(0);
    this.formHoverRating.set(0);
    this.formBody.set('');
    this.submitError.set('');
  }
}
