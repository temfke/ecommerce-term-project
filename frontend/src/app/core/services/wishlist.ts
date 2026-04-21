import { Injectable, computed, signal, inject, effect } from '@angular/core';
import { Auth } from './auth';

const STORAGE_PREFIX = 'wishlist::';
const GUEST_KEY = `${STORAGE_PREFIX}guest`;

@Injectable({ providedIn: 'root' })
export class Wishlist {
  private readonly auth = inject(Auth);
  private currentKey = this.keyFor(this.auth.currentUser()?.userId ?? null);
  private readonly _ids = signal<number[]>(this.load(this.currentKey));

  readonly ids = this._ids.asReadonly();
  readonly count = computed(() => this._ids().length);

  constructor() {
    effect(() => {
      const user = this.auth.currentUser();
      const nextKey = this.keyFor(user?.userId ?? null);
      if (nextKey !== this.currentKey) {
        this.currentKey = nextKey;
        this._ids.set(this.load(nextKey));
      }
    });
  }

  has(productId: number): boolean {
    return this._ids().includes(productId);
  }

  toggle(productId: number): boolean {
    let nowSaved = false;
    this._ids.update(list => {
      if (list.includes(productId)) {
        return list.filter(id => id !== productId);
      }
      nowSaved = true;
      return [...list, productId];
    });
    this.persist();
    return nowSaved;
  }

  remove(productId: number) {
    this._ids.update(list => list.filter(id => id !== productId));
    this.persist();
  }

  private keyFor(userId: number | null): string {
    return userId == null ? GUEST_KEY : `${STORAGE_PREFIX}${userId}`;
  }

  private load(key: string): number[] {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.filter(n => typeof n === 'number') : [];
    } catch {
      return [];
    }
  }

  private persist() {
    try {
      localStorage.setItem(this.currentKey, JSON.stringify(this._ids()));
    } catch {
      // ignore quota errors
    }
  }
}
