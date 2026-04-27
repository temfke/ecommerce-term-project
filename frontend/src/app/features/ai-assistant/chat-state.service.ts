import { Injectable, computed, inject, signal } from '@angular/core';
import { Api } from '../../core/services/api';
import { ChatResponse, ChatTurn } from '../../core/models/chat.model';

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  text: string;
  payload?: ChatResponse;
}

/** Singleton (`providedIn: 'root'`) so the messages and draft survive route
 *  navigation. On first use it loads persisted history from the backend, then
 *  every send/clear writes through both the local signal and the backend. */
@Injectable({ providedIn: 'root' })
export class ChatStateService {
  private readonly api = inject(Api);

  readonly messages = signal<ChatMessage[]>([]);
  readonly draft = signal('');
  readonly loading = signal(false);
  readonly errorText = signal('');
  readonly historyLoaded = signal(false);

  readonly hasMessages = computed(() => this.messages().length > 0);

  private nextId = 1;

  ensureHistoryLoaded(): void {
    if (this.historyLoaded()) return;
    this.historyLoaded.set(true);
    this.api.getChatHistory().subscribe({
      next: (entries) => {
        const loaded: ChatMessage[] = entries.map(e => ({
          id: this.nextId++,
          role: e.role,
          text: e.content,
          payload: e.payload ?? undefined,
        }));
        this.messages.set(loaded);
      },
      error: () => this.historyLoaded.set(false),
    });
  }

  clear(): void {
    this.api.clearChatHistory().subscribe({
      next: () => this.messages.set([]),
    });
  }

  send(question: string): void {
    const q = question.trim();
    if (!q || this.loading()) return;

    this.errorText.set('');
    this.append({ id: this.nextId++, role: 'user', text: q });
    this.draft.set('');
    this.loading.set(true);

    const history: ChatTurn[] = this.messages()
      .slice(-10)
      .map(m => ({ role: m.role, content: m.text }));

    this.api.askChat({ question: q, history }).subscribe({
      next: (res) => {
        this.append({ id: this.nextId++, role: 'assistant', text: res.narrative, payload: res });
        this.loading.set(false);
      },
      error: (err) => {
        this.errorText.set(err?.error?.message ?? 'Sorry, I couldn\'t reach the assistant. Try again.');
        this.loading.set(false);
      },
    });
  }

  private append(m: ChatMessage): void {
    this.messages.update(list => [...list, m]);
  }
}
