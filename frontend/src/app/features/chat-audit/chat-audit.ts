import { Component, ChangeDetectionStrategy, inject, signal, computed, OnInit } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { Api } from '../../core/services/api';
import { ChatAudit } from '../../core/models/chat-audit.model';
import { InfiniteScrollDirective } from '../../shared/directives/infinite-scroll.directive';

const PAGE_SIZE = 200;

@Component({
  selector: 'app-chat-audit',
  imports: [DatePipe, DecimalPipe, InfiniteScrollDirective],
  templateUrl: './chat-audit.html',
  styleUrl: './chat-audit.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ChatAuditPage implements OnInit {
  private readonly api = inject(Api);

  readonly entries = signal<ChatAudit[]>([]);
  readonly loading = signal(true);
  readonly statusFilter = signal('');
  readonly hasMore = signal(false);
  readonly expandedId = signal<number | null>(null);

  readonly summary = computed(() => {
    const list = this.entries();
    const total = list.length;
    const blocked = list.filter(e => e.status === 'BLOCKED').length;
    const answered = list.filter(e => e.status === 'ANSWER').length;
    const rateLimited = list.filter(e => e.rateLimited).length;
    return { total, blocked, answered, rateLimited };
  });

  ngOnInit() {
    this.load(true);
  }

  onFilterChange(status: string) {
    this.statusFilter.set(status);
    this.load(true);
  }

  loadMore() {
    if (!this.hasMore() || this.loading()) return;
    this.load(false);
  }

  toggleExpanded(id: number) {
    this.expandedId.update(curr => (curr === id ? null : id));
  }

  private load(reset: boolean) {
    this.loading.set(true);
    const status = this.statusFilter() || undefined;
    const offset = reset ? 0 : this.entries().length;
    this.api.getChatAudit({ status, limit: PAGE_SIZE, offset }).subscribe({
      next: (data) => {
        this.entries.update(curr => reset ? data : [...curr, ...data]);
        this.hasMore.set(data.length === PAGE_SIZE);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
