export type ShipmentStatus = 'PENDING' | 'PROCESSING' | 'IN_TRANSIT' | 'DELIVERED' | 'RETURNED';

export interface Shipment {
  id: number;
  orderId: number;
  trackingId: string;
  carrier: string;
  warehouseBlock: string;
  modeOfShipment: string;
  destination: string;
  status: ShipmentStatus;
  customerName: string;
  estimatedDelivery: string;
  shippedAt?: string;
  deliveredAt?: string;
  createdAt: string;
}
