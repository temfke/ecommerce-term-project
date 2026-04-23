import { Component, ChangeDetectionStrategy } from '@angular/core';

@Component({
  selector: 'app-ai-assistant',
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './ai-assistant.scss',
  template: `
    <div class="page ai-page">
      <div class="ai-card">
        <div class="ai-icon" aria-hidden="true">🤖</div>
        <h2>AI Assistant</h2>
        <p class="ai-tag">Coming soon</p>
        <p class="ai-description">
          Ask natural-language questions about your sales, customers, and inventory.
          Get instant insights, generate product descriptions, and let the assistant
          summarize reviews for you.
        </p>
        <ul class="ai-features">
          <li><span aria-hidden="true">💬</span> Chat with your storefront data</li>
          <li><span aria-hidden="true">📊</span> Auto-generated analytics summaries</li>
          <li><span aria-hidden="true">✍️</span> Product copy &amp; review digests</li>
          <li><span aria-hidden="true">🔔</span> Anomaly &amp; trend alerts</li>
        </ul>
      </div>
    </div>
  `,
})
export class AiAssistant {}
