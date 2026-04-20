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
  myVote?: 'HELPFUL' | 'NOT_HELPFUL' | null;
  createdAt: string;
}

export type ReviewVoteType = 'HELPFUL' | 'NOT_HELPFUL';

export interface ReviewRequest {
  productId: number;
  starRating: number;
  reviewBody?: string;
}
