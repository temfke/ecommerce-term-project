export interface Product {
  id: number;
  name: string;
  description: string;
  sku: string;
  unitPrice: number;
  stockQuantity: number;
  imageUrl?: string;
  active: boolean;
  storeId: number;
  storeName: string;
  categoryId?: number;
  categoryName?: string;
  createdAt: string;
}

export interface ProductRequest {
  name: string;
  description?: string;
  sku: string;
  unitPrice: number;
  stockQuantity: number;
  categoryId?: number;
  storeId: number;
  imageUrl?: string;
}
