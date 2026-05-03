import { Component, ChangeDetectionStrategy, inject, computed, AfterViewChecked, OnInit, effect, ElementRef, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DecimalPipe } from '@angular/common';
import { Auth } from '../../core/services/auth';
import { ChatStateService } from './chat-state.service';

@Component({
  selector: 'app-ai-assistant',
  imports: [FormsModule, DecimalPipe],
  templateUrl: './ai-assistant.html',
  styleUrl: './ai-assistant.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AiAssistant implements OnInit, AfterViewChecked {
  private readonly auth = inject(Auth);
  private readonly state = inject(ChatStateService);
  private readonly scrollEl = viewChild<ElementRef<HTMLDivElement>>('scrollEl');

  readonly messages = this.state.messages;
  readonly draft = this.state.draft;
  readonly loading = this.state.loading;
  readonly errorText = this.state.errorText;
  readonly hasMessages = this.state.hasMessages;

  readonly userName = computed(() => this.auth.currentUser()?.firstName ?? 'there');
  readonly userRole = computed(() => this.auth.userRole());

  // Suggested prompts are tailored to what the role actually has access to.
  // Admins ask platform-wide questions; corporate users ask about their own
  // store(s) and their rivals; individuals ask about their own purchases.
  private readonly adminSuggestions = [
    'Total revenues of every store',
    'Show monthly revenue',
    'Top 5 selling products this month',
    'Revenue of the platform',
    'Top seller store in electronics category',
    'List products that received 1-star reviews',
    "Show this week's shipment status",
    'How much did Aegean Outfitters make?',
  ];
  private readonly corporateSuggestions = [
    'Total revenue of my store',
    'Show monthly revenue',
    'Top 5 selling products in my store this month',
    'Which products are below 10 in stock?',
    'Who are my rivals?',
    'List products that received 1-star reviews',
    "Show this week's shipment status",
    'How did sales change vs last month?',
  ];
  private readonly individualSuggestions = [
    'Show my last purchase details',
    'What is the percentage of my last purchase in total value of my last 10 purchases?',
    'Show the categoric breakdown of my last 10 purchases',
    'Which categories did I spend the most on this month?',
    'What are my recent orders?',
    'Best seller store in electronics category',
    'Show monthly revenue trend',
    'Show my last 5 reviews',
  ];

  readonly suggestions = computed(() => {
    switch (this.userRole()) {
      case 'ADMIN': return this.adminSuggestions;
      case 'CORPORATE': return this.corporateSuggestions;
      case 'INDIVIDUAL': return this.individualSuggestions;
      default: return this.individualSuggestions;
    }
  });

  readonly scopeLabel = computed(() => {
    const role = this.userRole();
    if (role === 'ADMIN') return 'platform';
    if (role === 'CORPORATE') return 'store';
    return 'account';
  });

  private shouldScroll = false;

  constructor() {
    // Auto-scroll whenever the message list grows.
    effect(() => {
      this.messages();
      this.shouldScroll = true;
    });
  }

  ngOnInit() {
    this.state.ensureHistoryLoaded();
  }

  ngAfterViewChecked() {
    if (this.shouldScroll) {
      const el = this.scrollEl()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
      this.shouldScroll = false;
    }
  }

  send(text?: string) {
    this.state.send(text ?? this.draft());
  }

  useSuggestion(s: string) { this.send(s); }

  onSubmit(event: Event) {
    event.preventDefault();
    this.send();
  }

  clearChat() {
    if (!confirm('Clear the entire chat history? This cannot be undone.')) return;
    this.state.clear();
  }

  // Vertical-bar chart geometry. Returns SVG-ready bars + Y-axis ticks.
  readonly chartPalette = [
    '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
    '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#14b8a6',
    '#a855f7', '#22c55e', '#eab308', '#f43f5e', '#3b82f6',
  ];

  verticalBars(rows: { label: string; value: number }[] | null | undefined): {
    bars: { label: string; value: number; x: number; y: number; w: number; h: number; color: string; valueText: string }[];
    ticks: { y: number; label: string }[];
    chartWidth: number;
    chartHeight: number;
    plotLeft: number;
    plotTop: number;
    plotBottom: number;
  } | null {
    if (!rows || rows.length === 0) return null;
    const data = rows.slice(0, 15);
    const max = Math.max(...data.map(r => r.value), 1);
    const niceMax = this.niceCeiling(max);

    const chartWidth = 540;
    const chartHeight = 220;
    const plotLeft = 56;
    const plotRight = 12;
    const plotTop = 12;
    const plotBottom = 40;
    const innerW = chartWidth - plotLeft - plotRight;
    const innerH = chartHeight - plotTop - plotBottom;

    const slotW = innerW / data.length;
    const barW = Math.min(40, slotW * 0.65);

    const bars = data.map((r, i) => {
      const h = (r.value / niceMax) * innerH;
      return {
        label: r.label,
        value: r.value,
        valueText: this.formatShort(r.value),
        x: plotLeft + i * slotW + (slotW - barW) / 2,
        y: plotTop + innerH - h,
        w: barW,
        h,
        color: this.chartPalette[i % this.chartPalette.length],
      };
    });

    const tickCount = 4;
    const ticks = Array.from({ length: tickCount + 1 }, (_, i) => {
      const value = (niceMax / tickCount) * i;
      return {
        y: plotTop + innerH - (value / niceMax) * innerH,
        label: this.formatShort(value),
      };
    });

    return { bars, ticks, chartWidth, chartHeight, plotLeft, plotTop, plotBottom };
  }

  // Line chart geometry. Returns the line path, area fill path, and axis grid.
  lineChart(rows: { label: string; value: number }[] | null | undefined): {
    linePath: string;
    areaPath: string;
    points: { x: number; y: number; label: string; valueText: string }[];
    ticks: { y: number; label: string }[];
    xLabels: { x: number; label: string }[];
    chartWidth: number;
    chartHeight: number;
  } | null {
    if (!rows || rows.length < 2) return null;
    const data = rows.slice(0, 30);
    const max = Math.max(...data.map(r => r.value), 1);
    const niceMax = this.niceCeiling(max);

    const chartWidth = 540;
    const chartHeight = 220;
    const plotLeft = 56;
    const plotRight = 12;
    const plotTop = 12;
    const plotBottom = 36;
    const innerW = chartWidth - plotLeft - plotRight;
    const innerH = chartHeight - plotTop - plotBottom;

    const stepX = data.length > 1 ? innerW / (data.length - 1) : 0;
    const points = data.map((r, i) => ({
      x: plotLeft + i * stepX,
      y: plotTop + innerH - (r.value / niceMax) * innerH,
      label: r.label,
      valueText: this.formatShort(r.value),
    }));

    const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
    const areaPath =
      `M ${points[0].x.toFixed(1)} ${(plotTop + innerH).toFixed(1)} ` +
      points.map(p => `L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ') +
      ` L ${points[points.length - 1].x.toFixed(1)} ${(plotTop + innerH).toFixed(1)} Z`;

    const tickCount = 4;
    const ticks = Array.from({ length: tickCount + 1 }, (_, i) => {
      const value = (niceMax / tickCount) * i;
      return {
        y: plotTop + innerH - (value / niceMax) * innerH,
        label: this.formatShort(value),
      };
    });

    // Show at most 6 X-axis labels evenly spaced
    const labelStep = Math.max(1, Math.ceil(data.length / 6));
    const xLabels = points
      .map((p, i) => ({ x: p.x, label: data[i].label, idx: i }))
      .filter(l => l.idx % labelStep === 0)
      .map(({ x, label }) => ({ x, label }));

    return { linePath, areaPath, points, ticks, xLabels, chartWidth, chartHeight };
  }

  // Pie/donut chart geometry. Returns one SVG arc segment per row.
  pieSegments(rows: { label: string; value: number }[] | null | undefined): {
    label: string; value: number; pct: number; path: string; color: string;
  }[] {
    if (!rows || rows.length === 0) return [];
    const total = rows.reduce((sum, r) => sum + r.value, 0);
    if (total <= 0) return [];

    const cx = 100, cy = 100, rOuter = 90, rInner = 50;

    let cursor = -Math.PI / 2;
    return rows.map((r, i) => {
      const slice = (r.value / total) * Math.PI * 2;
      const start = cursor;
      const end = cursor + slice;
      cursor = end;

      const largeArc = slice > Math.PI ? 1 : 0;
      const x0o = cx + rOuter * Math.cos(start), y0o = cy + rOuter * Math.sin(start);
      const x1o = cx + rOuter * Math.cos(end),   y1o = cy + rOuter * Math.sin(end);
      const x0i = cx + rInner * Math.cos(end),   y0i = cy + rInner * Math.sin(end);
      const x1i = cx + rInner * Math.cos(start), y1i = cy + rInner * Math.sin(start);

      const path = [
        `M ${x0o} ${y0o}`,
        `A ${rOuter} ${rOuter} 0 ${largeArc} 1 ${x1o} ${y1o}`,
        `L ${x0i} ${y0i}`,
        `A ${rInner} ${rInner} 0 ${largeArc} 0 ${x1i} ${y1i}`,
        'Z',
      ].join(' ');

      return {
        label: r.label,
        value: r.value,
        pct: (r.value / total) * 100,
        path,
        color: this.chartPalette[i % this.chartPalette.length],
      };
    });
  }

  private niceCeiling(value: number): number {
    if (value <= 0) return 1;
    const exp = Math.floor(Math.log10(value));
    const base = Math.pow(10, exp);
    const candidates = [1, 2, 2.5, 5, 10];
    for (const c of candidates) {
      if (value <= c * base) return c * base;
    }
    return 10 * base;
  }

  formatShort(v: number): string {
    if (v === 0) return '0';
    const abs = Math.abs(v);
    if (abs >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
    if (abs >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
    if (abs >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
    if (abs < 10 && abs % 1 !== 0) return v.toFixed(2);
    return v.toFixed(0);
  }
}
