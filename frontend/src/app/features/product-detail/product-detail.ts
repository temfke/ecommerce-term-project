import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DecimalPipe, DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { Cart } from '../../core/services/cart';
import { Product } from '../../core/models/product.model';
import { Review } from '../../core/models/review.model';

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

  readonly formRating = signal(0);
  readonly formHoverRating = signal(0);
  readonly formBody = signal('');
  readonly submitting = signal(false);
  readonly submitError = signal('');
  readonly submitSuccess = signal(false);

  readonly canReview = computed(() => this.auth.isAuthenticated());

  readonly maxAddable = computed(() => {
    const p = this.product();
    if (!p) return 0;
    return Math.max(0, p.stockQuantity - this.cart.quantityOf(p.id));
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

    this.api.getReviewsByProduct(id).subscribe({
      next: (r) => {
        this.reviews.set(r);
        this.reviewsLoading.set(false);
      },
      error: () => this.reviewsLoading.set(false),
    });
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
      next: () => {
        this.submitting.set(false);
        this.submitSuccess.set(true);
        this.resetReviewForm();
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
