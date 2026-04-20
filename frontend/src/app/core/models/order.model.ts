export type OrderStatus = 'PENDING' | 'CONFIRMED' | 'PROCESSING' | 'SHIPPED' | 'DELIVERED' | 'CANCELLED' | 'RETURNED';
export type PaymentMethod = 'CREDIT_CARD' | 'DEBIT_CARD' | 'PAYPAL' | 'BANK_TRANSFER' | 'CASH_ON_DELIVERY';

export interface OrderItem {
  id: number;
  productId: number;
  productName: string;
  quantity: number;
  price: number;
}

export interface Order {
  id: number;
  userId: number;
  customerName: string;
  customerEmail: string;
  storeId: number;
  storeName: string;
  status: OrderStatus;
  grandTotal: number;
  paymentMethod: PaymentMethod;
  shippingAddress: string;
  items: OrderItem[];
  createdAt: string;
}

export interface OrderRequest {
  storeId: number;
  items: { productId: number; quantity: number }[];
  paymentMethod: PaymentMethod;
  shippingAddress: string;
}

export interface CheckoutSessionRequest {
  storeId: number;
  items: { productId: number; quantity: number }[];
  shippingAddress?: string;
}

export interface CheckoutSessionResponse {
  sessionId: string;
  url: string;
}

export interface PaymentConfirmResponse {
  status: string;
  order?: Order;
}
