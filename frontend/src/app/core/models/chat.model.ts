export type ChatStatus = 'ANSWER' | 'GREETING' | 'OUT_OF_SCOPE' | 'BLOCKED';
export type ChartType = 'BAR' | 'LINE' | 'PIE' | 'NONE';

export interface ChatDataRow {
  label: string;
  value: number;
}

export interface ChatGuardrail {
  type: string;
  trigger: string;
  action: string;
}

export interface ChatTable {
  columns: string[];
  rows: (string | number | boolean | null)[][];
}

export interface ChatResponse {
  status: ChatStatus;
  narrative: string;
  title?: string | null;
  bullets?: string[] | null;
  insight?: string | null;
  sqlPreview?: string | null;
  rows?: ChatDataRow[] | null;
  chartType?: ChartType | null;
  table?: ChatTable | null;
  guardrail?: ChatGuardrail | null;
}

export interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  question: string;
  history?: ChatTurn[];
}
