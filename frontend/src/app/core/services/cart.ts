import { Injectable, computed, signal, inject, effect } from '@angular/core';
import { Product } from '../models/product.model';
import { Auth } from './auth';

export interface CartItem {
  productId: number;
  name: string;
  unitPrice: number;
  imageUrl?: string;
  storeId: number;
  storeName: string;
  quantity: number;
  stockQuantity: number;
}

const STORAGE_PREFIX = 'cart::';
const GUEST_KEY = `${STORAGE_PREFIX}guest`;

@Injectable({ providedIn: 'root' })
export class Cart {
  private readonly auth = inject(Auth);
  private currentKey = this.keyFor(this.auth.currentUser()?.userId ?? null);
  private readonly _items = signal<CartItem[]>(this.load(this.currentKey));

  readonly items = this._items.asReadonly();
  readonly count = computed(() => this._items().reduce((s, i) => s + i.quantity, 0));
  readonly subtotal = computed(() =>
    this._items().reduce((s, i) => s + i.quantity * i.unitPrice, 0));

  constructor() {
    effect(() => {
      const user = this.auth.currentUser();
      const nextKey = this.keyFor(user?.userId ?? null);
      if (nextKey !== this.currentKey) {
        this.currentKey = nextKey;
        this._items.set(this.load(nextKey));
      }
    });
  }

  quantityOf(productId: number): number {
    return this._items().find(i => i.productId === productId)?.quantity ?? 0;
  }

  add(product: Product, quantity = 1): { added: number; capped: boolean } {
    const qty = Math.max(1, Math.floor(quantity));
    const max = Math.max(0, product.stockQuantity);
    let result = { added: 0, capped: false };
    this._items.update(items => {
      const idx = items.findIndex(i => i.productId === product.id);
      const currentQty = idx >= 0 ? items[idx].quantity : 0;
      const allowed = Math.max(0, Math.min(qty, max - currentQty));
      result = { added: allowed, capped: allowed < qty };
      if (allowed === 0) return items;
      if (idx >= 0) {
        const next = [...items];
        next[idx] = {
          ...next[idx],
          quantity: currentQty + allowed,
          stockQuantity: max,
        };
        return next;
      }
      return [...items, {
        productId: product.id,
        name: product.name,
        unitPrice: product.unitPrice,
        imageUrl: product.imageUrl,
        storeId: product.storeId,
        storeName: product.storeName,
        quantity: allowed,
        stockQuantity: max,
      }];
    });
    if (result.added > 0) this.persist();
    return result;
  }

  setQuantity(productId: number, quantity: number) {
    if (quantity <= 0) { this.remove(productId); return; }
    this._items.update(items =>
      items.map(i => {
        if (i.productId !== productId) return i;
        const cap = i.stockQuantity ?? i.quantity;
        return { ...i, quantity: Math.min(quantity, cap) };
      }));
    this.persist();
  }

  remove(productId: number) {
    this._items.update(items => items.filter(i => i.productId !== productId));
    this.persist();
  }

  clear() {
    this._items.set([]);
    this.persist();
  }

  private keyFor(userId: number | null): string {
    return userId == null ? GUEST_KEY : `${STORAGE_PREFIX}${userId}`;
  }

  private load(key: string): CartItem[] {
    try {
      const raw = localStorage.getItem(key);
      if (raw) {
        const parsed = JSON.parse(raw) as CartItem[];
        return parsed.map(i => ({ ...i, stockQuantity: i.stockQuantity ?? i.quantity }));
      }
      const legacy = localStorage.getItem('cart');
      if (legacy && key === GUEST_KEY) {
        const parsed = JSON.parse(legacy) as CartItem[];
        localStorage.removeItem('cart');
        return parsed.map(i => ({ ...i, stockQuantity: i.stockQuantity ?? i.quantity }));
      }
      return [];
    } catch {
      return [];
    }
  }

  private persist() {
    try {
      localStorage.setItem(this.currentKey, JSON.stringify(this._items()));
    } catch {
      // ignore quota errors
    }
  }
}
