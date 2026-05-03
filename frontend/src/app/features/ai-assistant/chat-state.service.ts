import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { ChatResponse, ChatTurn } from '../../core/models/chat.model';

export interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  text: string;
  payload?: ChatResponse;
}

/** Singleton (`providedIn: 'root'`) so the messages and draft survive route
 *  navigation. On first use it loads persisted history from the backend, then
 *  every send/clear writes through both the local signal and the backend.
 *
 *  Chat state is per-user: when the authenticated user changes (login / logout
 *  / account swap) the in-memory messages are wiped so a previous user's
 *  history can never appear in the next user's session, even without a page
 *  reload. The backend is the source of truth and re-loads history scoped to
 *  the new user's id when the AI assistant page mounts again. */
@Injectable({ providedIn: 'root' })
export class ChatStateService {
  private readonly api = inject(Api);
  private readonly auth = inject(Auth);

  readonly messages = signal<ChatMessage[]>([]);
  readonly draft = signal('');
  readonly loading = signal(false);
  readonly errorText = signal('');
  readonly historyLoaded = signal(false);

  readonly hasMessages = computed(() => this.messages().length > 0);

  private nextId = 1;
  private activeUserId: number | null = null;

  constructor() {
    // React to login / logout / account swap. Comparing user ids covers the
    // case where the same singleton instance sees two different signed-in
    // accounts back to back without a full page reload.
    effect(() => {
      const uid = this.auth.currentUser()?.userId ?? null;
      if (uid === this.activeUserId) return;
      this.activeUserId = uid;
      this.resetState();
    });
  }

  ensureHistoryLoaded(): void {
    if (this.historyLoaded()) return;
    if (!this.auth.isAuthenticated()) return;
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

  private resetState(): void {
    this.messages.set([]);
    this.draft.set('');
    this.errorText.set('');
    this.historyLoaded.set(false);
    this.loading.set(false);
  }

  private append(m: ChatMessage): void {
    this.messages.update(list => [...list, m]);
  }
}
