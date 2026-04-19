import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { Router } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { Cart } from '../../core/services/cart';
import { Product, ProductRequest } from '../../core/models/product.model';
import { Store } from '../../core/models/store.model';
import { Category } from '../../core/models/dashboard.model';

type SortBy = 'id' | 'name' | 'unitPrice' | 'stockQuantity' | 'createdAt';
type SortDir = 'asc' | 'desc';

@Component({
  selector: 'app-products',
  imports: [DecimalPipe, ReactiveFormsModule],
  templateUrl: './products.html',
  styleUrl: './products.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Products implements OnInit {
  private readonly api = inject(Api);
  private readonly auth = inject(Auth);
  private readonly router = inject(Router);
  readonly cart = inject(Cart);
  private readonly fb = inject(FormBuilder);

  readonly products = signal<Product[]>([]);
  readonly stores = signal<Store[]>([]);
  readonly categories = signal<Category[]>([]);
  readonly loading = signal(true);
  readonly showForm = signal(false);
  readonly editingId = signal<number | null>(null);
  readonly error = signal('');

  readonly addedFlash = signal<{ id: number; msg: string } | null>(null);

  readonly search = signal('');
  readonly categoryFilter = signal<number | null>(null);
  readonly storeFilter = signal<number | null>(null);
  readonly sortBy = signal<SortBy>('id');
  readonly sortDir = signal<SortDir>('desc');

  readonly isAdmin = computed(() => this.auth.userRole() === 'ADMIN');
  readonly isCorporate = computed(() => this.auth.userRole() === 'CORPORATE');
  readonly canManage = computed(() => this.isAdmin() || this.isCorporate());

  readonly sortOptions: { value: SortBy; label: string }[] = [
    { value: 'id', label: 'Newest' },
    { value: 'name', label: 'Name' },
    { value: 'unitPrice', label: 'Price' },
    { value: 'stockQuantity', label: 'Stock' },
    { value: 'createdAt', label: 'Date Added' },
  ];

  readonly form = this.fb.nonNullable.group({
    name: ['', Validators.required],
    description: [''],
    sku: ['', Validators.required],
    unitPrice: [0, [Validators.required, Validators.min(0.01)]],
    stockQuantity: [0, [Validators.required, Validators.min(0)]],
    categoryId: [null as number | null],
    storeId: [null as number | null, Validators.required],
    imageUrl: [''],
  });

  ngOnInit() {
    this.loadProducts();
    this.api.getCategories().subscribe(c => this.categories.set(c));
    if (this.isCorporate()) {
      this.api.getMyStores().subscribe(s => this.stores.set(s));
    } else {
      this.api.getStores().subscribe(s => this.stores.set(s));
    }
  }

  loadProducts() {
    this.loading.set(true);
    this.api.getProducts({
      search: this.search() || undefined,
      categoryId: this.categoryFilter(),
      storeId: this.storeFilter(),
      sortBy: this.sortBy(),
      sortDir: this.sortDir(),
      limit: 100,
    }).subscribe({
      next: (data) => {
        this.products.set(data);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  onSearch(value: string) {
    this.search.set(value);
    this.loadProducts();
  }

  onCategoryChange(value: string) {
    this.categoryFilter.set(value ? Number(value) : null);
    this.loadProducts();
  }

  onStoreChange(value: string) {
    this.storeFilter.set(value ? Number(value) : null);
    this.loadProducts();
  }

  onSortByChange(value: string) {
    this.sortBy.set(value as SortBy);
    this.loadProducts();
  }

  toggleSortDir() {
    this.sortDir.update(d => d === 'asc' ? 'desc' : 'asc');
    this.loadProducts();
  }

  clearFilters() {
    this.search.set('');
    this.categoryFilter.set(null);
    this.storeFilter.set(null);
    this.sortBy.set('id');
    this.sortDir.set('desc');
    this.loadProducts();
  }

  openCreate() {
    this.editingId.set(null);
    const defaultStoreId = this.stores().length === 1 ? this.stores()[0].id : null;
    this.form.reset({
      name: '',
      description: '',
      sku: '',
      unitPrice: 0,
      stockQuantity: 0,
      categoryId: null,
      storeId: defaultStoreId,
      imageUrl: '',
    });
    this.showForm.set(true);
    this.error.set('');
  }

  openEdit(p: Product) {
    this.editingId.set(p.id);
    this.form.patchValue({
      name: p.name,
      description: p.description,
      sku: p.sku,
      unitPrice: p.unitPrice,
      stockQuantity: p.stockQuantity,
      categoryId: p.categoryId ?? null,
      storeId: p.storeId,
      imageUrl: p.imageUrl ?? '',
    });
    this.showForm.set(true);
    this.error.set('');
  }

  closeForm() {
    this.showForm.set(false);
    this.error.set('');
  }

  onSubmit() {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }
    const raw = this.form.getRawValue();
    if (raw.storeId == null) {
      this.error.set('Please select a store');
      return;
    }
    const req: ProductRequest = {
      name: raw.name,
      sku: raw.sku,
      unitPrice: raw.unitPrice,
      stockQuantity: raw.stockQuantity,
      storeId: raw.storeId,
      description: raw.description || undefined,
      categoryId: raw.categoryId ?? undefined,
      imageUrl: raw.imageUrl || undefined,
    };
    const id = this.editingId();
    const obs = id ? this.api.updateProduct(id, req) : this.api.createProduct(req);
    obs.subscribe({
      next: () => {
        this.closeForm();
        this.loadProducts();
      },
      error: (err) => this.error.set(err.error?.message ?? 'Failed to save product'),
    });
  }

  deleteProduct(id: number) {
    this.api.deleteProduct(id).subscribe(() => this.loadProducts());
  }

  openDetail(p: Product) {
    this.router.navigate(['/products', p.id]);
  }

  addToCart(p: Product, quantity = 1) {
    if (p.stockQuantity <= 0) return;
    const result = this.cart.add(p, quantity);
    let msg: string;
    if (result.added === 0) msg = 'Max in cart';
    else if (result.capped) msg = `Only ${result.added} added`;
    else msg = 'Added ✓';
    this.addedFlash.set({ id: p.id, msg });
    setTimeout(() => {
      if (this.addedFlash()?.id === p.id) this.addedFlash.set(null);
    }, 1500);
  }

  remainingStock(p: Product): number {
    return Math.max(0, p.stockQuantity - this.cart.quantityOf(p.id));
  }
}
