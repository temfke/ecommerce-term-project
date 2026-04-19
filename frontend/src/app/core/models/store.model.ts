export type StoreStatus = 'PENDING_APPROVAL' | 'OPEN' | 'CLOSED' | 'SUSPENDED';

export interface Store {
  id: number;
  name: string;
  description: string;
  logoUrl?: string;
  status: StoreStatus;
  ownerId: number;
  ownerName: string;
  createdAt: string;
}

export interface StoreRequest {
  name: string;
  description?: string;
  logoUrl?: string;
}
