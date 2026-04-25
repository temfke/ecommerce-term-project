import { Component, ChangeDetectionStrategy, inject, signal, computed, AfterViewChecked, ElementRef, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DecimalPipe } from '@angular/common';
import { Api } from '../../core/services/api';
import { Auth } from '../../core/services/auth';
import { ChatResponse, ChatTurn } from '../../core/models/chat.model';

interface Message {
  id: number;
  role: 'user' | 'assistant';
  text: string;
  payload?: ChatResponse;
}

@Component({
  selector: 'app-ai-assistant',
  imports: [FormsModule, DecimalPipe],
  templateUrl: './ai-assistant.html',
  styleUrl: './ai-assistant.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AiAssistant implements AfterViewChecked {
  private readonly api = inject(Api);
  private readonly auth = inject(Auth);
  private readonly scrollEl = viewChild<ElementRef<HTMLDivElement>>('scrollEl');

  readonly messages = signal<Message[]>([]);
  readonly draft = signal('');
  readonly loading = signal(false);
  readonly errorText = signal('');

  private nextId = 1;
  private shouldScroll = false;

  readonly suggestions = [
    'How did sales change vs last month?',
    'Which products are below 10 in stock?',
    'Who are my top 5 customers?',
    'What is the total value of pending orders?',
    'Which category has the highest return rate?',
    'Show this week\'s shipment status',
    'List products that received 1-star reviews',
    'Show monthly revenue as a chart',
  ];

  readonly userName = computed(() => this.auth.currentUser()?.firstName ?? 'there');
  readonly userRole = computed(() => this.auth.userRole());
  readonly hasMessages = computed(() => this.messages().length > 0);

  readonly scopeLabel = computed(() => {
    const role = this.userRole();
    if (role === 'ADMIN') return 'platform';
    if (role === 'CORPORATE') return 'store';
    return 'account';
  });

  ngAfterViewChecked() {
    if (this.shouldScroll) {
      const el = this.scrollEl()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
      this.shouldScroll = false;
    }
  }

  send(text?: string) {
    const q = (text ?? this.draft()).trim();
    if (!q || this.loading()) return;

    this.errorText.set('');
    this.draft.set('');
    this.appendMessage({ id: this.nextId++, role: 'user', text: q });

    const history: ChatTurn[] = this.messages()
      .slice(-10)
      .map(m => ({ role: m.role, content: m.text }));

    this.loading.set(true);
    this.api.askChat({ question: q, history }).subscribe({
      next: (res) => {
        this.appendMessage({ id: this.nextId++, role: 'assistant', text: res.narrative, payload: res });
        this.loading.set(false);
      },
      error: (err) => {
        this.errorText.set(err?.error?.message ?? 'Sorry, I couldn\'t reach the assistant. Try again.');
        this.loading.set(false);
      },
    });
  }

  useSuggestion(s: string) { this.send(s); }

  onSubmit(event: Event) {
    event.preventDefault();
    this.send();
  }

  maxValue(rows: { value: number }[] | null | undefined): number {
    if (!rows || rows.length === 0) return 1;
    const max = Math.max(...rows.map(r => r.value));
    return max > 0 ? max : 1;
  }

  barWidth(value: number, rows: { value: number }[] | null | undefined): number {
    return Math.max(4, (value / this.maxValue(rows)) * 100);
  }

  private appendMessage(m: Message) {
    this.messages.update(list => [...list, m]);
    this.shouldScroll = true;
  }
}
