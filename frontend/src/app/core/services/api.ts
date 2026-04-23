import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Product, ProductRequest } from '../models/product.model';
import { Order, OrderRequest, CheckoutSessionRequest, CheckoutSessionResponse, PaymentConfirmResponse } from '../models/order.model';
import { Store, StoreRequest } from '../models/store.model';
import { Review, ReviewRequest, ReviewVoteType } from '../models/review.model';
import { Shipment } from '../models/shipment.model';
import { User, AuthResponse } from '../models/user.model';
import { Address, AddressRequest } from '../models/address.model';
import { DashboardStats, Category } from '../models/dashboard.model';

@Injectable({ providedIn: 'root' })
export class Api {
  private readonly API = 'http://localhost:8080/api';
  private readonly http = inject(HttpClient);

  // Products
  getProducts(opts: {
    search?: string;
    categoryId?: number | null;
    storeId?: number | null;
    sortBy?: string;
    sortDir?: 'asc' | 'desc';
    limit?: number;
    offset?: number;
  } = {}) {
    const parts: string[] = [];
    if (opts.search) parts.push(`search=${encodeURIComponent(opts.search)}`);
    if (opts.categoryId != null) parts.push(`categoryId=${opts.categoryId}`);
    if (opts.storeId != null) parts.push(`storeId=${opts.storeId}`);
    if (opts.sortBy) parts.push(`sortBy=${opts.sortBy}`);
    if (opts.sortDir) parts.push(`sortDir=${opts.sortDir}`);
    if (opts.limit != null) parts.push(`limit=${opts.limit}`);
    if (opts.offset != null) parts.push(`offset=${opts.offset}`);
    const qs = parts.length ? `?${parts.join('&')}` : '';
    return this.http.get<Product[]>(`${this.API}/products${qs}`);
  }
  getProduct(id: number) { return this.http.get<Product>(`${this.API}/products/${id}`); }
  getProductsByStore(storeId: number) { return this.http.get<Product[]>(`${this.API}/products/store/${storeId}`); }
  createProduct(req: ProductRequest) { return this.http.post<Product>(`${this.API}/products`, req); }
  updateProduct(id: number, req: ProductRequest) { return this.http.put<Product>(`${this.API}/products/${id}`, req); }
  deleteProduct(id: number) { return this.http.delete<void>(`${this.API}/products/${id}`); }

  // Orders
  getMyOrders() { return this.http.get<Order[]>(`${this.API}/orders/my`); }
  getOrders() { return this.http.get<Order[]>(`${this.API}/orders`); }
  getOrdersByStore(storeId: number) { return this.http.get<Order[]>(`${this.API}/orders/store/${storeId}`); }
  getOrder(id: number) { return this.http.get<Order>(`${this.API}/orders/${id}`); }
  createOrder(req: OrderRequest) { return this.http.post<Order>(`${this.API}/orders`, req); }
  updateOrderStatus(id: number, status: string) {
    return this.http.patch<Order>(`${this.API}/orders/${id}/status?status=${status}`, {});
  }

  // Payments (Stripe Checkout)
  createCheckoutSession(req: CheckoutSessionRequest) {
    return this.http.post<CheckoutSessionResponse>(`${this.API}/payments/checkout-session`, req);
  }
  confirmPayment(sessionId: string) {
    return this.http.get<PaymentConfirmResponse>(`${this.API}/payments/confirm?session_id=${encodeURIComponent(sessionId)}`);
  }

  // Stores
  getStores() { return this.http.get<Store[]>(`${this.API}/stores`); }
  getMyStores() { return this.http.get<Store[]>(`${this.API}/stores/my`); }
  getStore(id: number) { return this.http.get<Store>(`${this.API}/stores/${id}`); }
  createStore(req: StoreRequest) { return this.http.post<Store>(`${this.API}/stores`, req); }
  updateStore(id: number, req: StoreRequest) { return this.http.put<Store>(`${this.API}/stores/${id}`, req); }
  updateStoreStatus(id: number, status: string) {
    return this.http.patch<Store>(`${this.API}/stores/${id}/status?status=${status}`, {});
  }

  // Reviews
  getReviewsByProduct(productId: number) { return this.http.get<Review[]>(`${this.API}/reviews/product/${productId}`); }
  getProductRatingSummary(productId: number) {
    return this.http.get<{ count: number; averageRating: number }>(`${this.API}/reviews/product/${productId}/summary`);
  }
  getMyReviewsForProduct(productId: number) {
    return this.http.get<Review[]>(`${this.API}/reviews/product/${productId}/mine`);
  }
  getMyReviews() { return this.http.get<Review[]>(`${this.API}/reviews/my`); }
  getReviews() { return this.http.get<Review[]>(`${this.API}/reviews`); }
  getReviewsByStore(storeId: number) { return this.http.get<Review[]>(`${this.API}/reviews/store/${storeId}`); }
  createReview(req: ReviewRequest) { return this.http.post<Review>(`${this.API}/reviews`, req); }
  voteOnReview(id: number, type: ReviewVoteType) {
    return this.http.post<Review>(`${this.API}/reviews/${id}/vote?type=${type}`, {});
  }
  deleteReview(id: number) { return this.http.delete<void>(`${this.API}/reviews/${id}`); }

  // Shipments
  getShipments(status?: string) {
    const params = status ? `?status=${status}` : '';
    return this.http.get<Shipment[]>(`${this.API}/shipments${params}`);
  }
  getShipmentByOrder(orderId: number) { return this.http.get<Shipment>(`${this.API}/shipments/order/${orderId}`); }
  createShipment(body: Record<string, unknown>) { return this.http.post<Shipment>(`${this.API}/shipments`, body); }
  updateShipmentStatus(id: number, status: string) {
    return this.http.patch<Shipment>(`${this.API}/shipments/${id}/status?status=${status}`, {});
  }

  // Users
  getCurrentUser() { return this.http.get<User>(`${this.API}/users/me`); }
  getUsers(role?: string) {
    const params = role ? `?role=${role}` : '';
    return this.http.get<User[]>(`${this.API}/users${params}`);
  }
  toggleUserStatus(id: number) { return this.http.patch<User>(`${this.API}/users/${id}/toggle-status`, {}); }
  deleteUser(id: number) { return this.http.delete<void>(`${this.API}/users/${id}`); }

  // Addresses
  getMyAddresses() { return this.http.get<Address[]>(`${this.API}/addresses`); }
  createAddress(req: AddressRequest) { return this.http.post<Address>(`${this.API}/addresses`, req); }
  updateAddress(id: number, req: AddressRequest) { return this.http.put<Address>(`${this.API}/addresses/${id}`, req); }
  setDefaultAddress(id: number) { return this.http.patch<Address>(`${this.API}/addresses/${id}/default`, {}); }
  deleteAddress(id: number) { return this.http.delete<void>(`${this.API}/addresses/${id}`); }

  // Email verification
  verifyEmail(token: string) { return this.http.post<AuthResponse>(`http://localhost:8080/api/auth/verify`, { token }); }
  resendEmailVerification() { return this.http.post<AuthResponse>(`http://localhost:8080/api/auth/resend-verification`, {}); }

  // Categories
  getCategories() { return this.http.get<Category[]>(`${this.API}/categories`); }
  createCategory(body: Record<string, unknown>) { return this.http.post<Category>(`${this.API}/categories`, body); }
  deleteCategory(id: number) { return this.http.delete<void>(`${this.API}/categories/${id}`); }

  // Analytics
  getAdminDashboard() { return this.http.get<DashboardStats>(`${this.API}/analytics/admin/dashboard`); }
  getCorporateDashboard(storeId: number) {
    return this.http.get<DashboardStats>(`${this.API}/analytics/corporate/dashboard/${storeId}`);
  }
}
