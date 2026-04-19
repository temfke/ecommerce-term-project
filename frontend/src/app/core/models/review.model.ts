export interface Review {
  id: number;
  userId: number;
  userName: string;
  productId: number;
  productName: string;
  starRating: number;
  reviewBody: string;
  sentiment?: string;
  helpfulVotes: number;
  totalVotes: number;
  createdAt: string;
}

export interface ReviewRequest {
  productId: number;
  starRating: number;
  reviewBody?: string;
}
