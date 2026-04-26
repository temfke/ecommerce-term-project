export interface ChatAudit {
  id: number;
  userId: number;
  userEmail: string | null;
  role: string;
  question: string;
  status: 'ANSWER' | 'GREETING' | 'OUT_OF_SCOPE' | 'BLOCKED' | string;
  blockedBy: string | null;
  guardrailTrigger: string | null;
  sqlPreview: string | null;
  rowCount: number | null;
  executionMs: number | null;
  rateLimited: boolean;
  createdAt: string;
}
