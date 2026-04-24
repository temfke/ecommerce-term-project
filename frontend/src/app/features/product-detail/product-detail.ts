import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DecimalPipe, DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { Cart } from '../../core/services/cart';
import { Wishlist } from '../../core/services/wishlist';
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
  readonly wishlist = inject(Wishlist);

  readonly product = signal<Product | null>(null);
  readonly reviews = signal<Review[]>([]);
  readonly summary = signal<{ count: number; averageRating: number }>({ count: 0, averageRating: 0 });
  readonly related = signal<Product[]>([]);
  readonly loading = signal(true);
  readonly reviewsLoading = signal(true);
  readonly notFound = signal(false);
  readonly detailQty = signal(1);
  readonly addedFlash = signal(false);
  readonly buying = signal(false);
  readonly shareFlash = signal('');
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
  readonly isAdmin = computed(() => this.auth.userRole() === 'ADMIN');
  readonly isCorporate = computed(() => this.auth.userRole() === 'CORPORATE');
  readonly canBuy = computed(() => !this.isAdmin() && !this.isCorporate());
  readonly inWishlist = computed(() => {
    const p = this.product();
    return p != null && this.wishlist.ids().includes(p.id);
  });

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
        this.loadRelated(p);
      },
      error: () => {
        this.notFound.set(true);
        this.loading.set(false);
      },
    });

    this.reloadReviews(id);
  }

  private loadRelated(p: Product) {
    this.related.set([]);
    if (p.categoryId == null) return;
    this.api.getProducts({ categoryId: p.categoryId, limit: 12 }).subscribe({
      next: (list) => {
        const filtered = list.filter(x => x.id !== p.id).slice(0, 6);
        this.related.set(filtered);
      },
      error: () => this.related.set([]),
    });
  }

  private reloadReviews(id: number, pinned?: Review) {
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
          this.reviews.set(this.mergeReviews(recent, mine, pinned));
          this.reviewsLoading.set(false);
        },
        error: () => this.reviewsLoading.set(false),
      });
    } else {
      this.api.getReviewsByProduct(id).subscribe({
        next: (r) => {
          this.reviews.set(this.mergeReviews(r, [], pinned));
          this.reviewsLoading.set(false);
        },
        error: () => this.reviewsLoading.set(false),
      });
    }
  }

  private mergeReviews(recent: Review[], mine: Review[], pinned?: Review): Review[] {
    const seen = new Set<number>();
    const merged: Review[] = [];
    if (pinned) { merged.push(pinned); seen.add(pinned.id); }
    for (const r of recent) {
      if (!seen.has(r.id)) { merged.push(r); seen.add(r.id); }
    }
    for (const r of mine) {
      if (!seen.has(r.id)) { merged.push(r); seen.add(r.id); }
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

  buyNow() {
    const p = this.product();
    if (!p || this.maxAddable() <= 0) return;
    if (!this.auth.isAuthenticated()) {
      this.router.navigate(['/login']);
      return;
    }
    this.cart.add(p, this.detailQty());
    this.buying.set(true);
    this.router.navigate(['/orders']);
  }

  toggleWishlist() {
    const p = this.product();
    if (!p) return;
    const saved = this.wishlist.toggle(p.id);
    this.shareFlash.set(saved ? 'Saved to wishlist' : 'Removed from wishlist');
    setTimeout(() => this.shareFlash.set(''), 1500);
  }

  shareProduct() {
    const p = this.product();
    if (!p) return;
    const url = window.location.href;
    const data = { title: p.name, text: p.name, url };
    const nav = window.navigator as Navigator & { share?: (d: ShareData) => Promise<void> };
    if (typeof nav.share === 'function') {
      nav.share(data).catch(() => this.copyLink(url));
      return;
    }
    this.copyLink(url);
  }

  private copyLink(url: string) {
    const onSuccess = () => {
      this.shareFlash.set('Link copied');
      setTimeout(() => this.shareFlash.set(''), 1500);
    };
    if (window.navigator.clipboard?.writeText) {
      window.navigator.clipboard.writeText(url).then(onSuccess, () => {
        this.shareFlash.set('Copy failed');
        setTimeout(() => this.shareFlash.set(''), 1500);
      });
    } else {
      this.shareFlash.set('Copy not supported');
      setTimeout(() => this.shareFlash.set(''), 1500);
    }
  }

  goBack() {
    this.router.navigate(['/products']);
  }

  openRelated(p: Product) {
    this.router.navigate(['/products', p.id]);
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
        this.reloadReviews(p.id, created);
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

  deleteReview(review: Review) {
    const isOwner = this.isMyReview(review);
    if (!this.isAdmin() && !isOwner) return;
    const prompt = isOwner
      ? 'Delete your review? This cannot be undone.'
      : `Delete this review by ${review.userName}? This cannot be undone.`;
    if (!confirm(prompt)) return;
    this.api.deleteReview(review.id).subscribe({
      next: () => {
        this.reviews.update(list => list.filter(r => r.id !== review.id));
        this.summary.update(s => {
          const newCount = Math.max(0, s.count - 1);
          if (newCount === 0) return { count: 0, averageRating: 0 };
          const totalStars = s.averageRating * s.count - review.starRating;
          return { count: newCount, averageRating: Math.round((totalStars / newCount) * 10) / 10 };
        });
      },
      error: (err) => this.voteError.set(err?.error?.message ?? 'Failed to delete review.'),
    });
  }
}
