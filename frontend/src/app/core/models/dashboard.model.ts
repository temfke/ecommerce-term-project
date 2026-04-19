export interface DashboardStats {
  totalRevenue: number;
  totalOrders: number;
  totalCustomers: number;
  avgRating: number;
  totalProducts: number;
  pendingOrders: number;
  shippedOrders: number;
  deliveredOrders: number;
}

export interface Category {
  id: number;
  name: string;
  description?: string;
  parent?: Category;
}
