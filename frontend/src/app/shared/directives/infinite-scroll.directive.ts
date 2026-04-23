import { Directive, ElementRef, OnDestroy, OnInit, output, inject, input } from '@angular/core';

@Directive({
  selector: '[appInfiniteScroll]',
})
export class InfiniteScrollDirective implements OnInit, OnDestroy {
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  readonly rootMargin = input('400px');
  readonly disabled = input(false);
  readonly endReached = output<void>();

  private observer: IntersectionObserver | null = null;

  ngOnInit() {
    this.observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting && !this.disabled()) {
          this.endReached.emit();
        }
      }
    }, { rootMargin: this.rootMargin() });
    this.observer.observe(this.host.nativeElement);
  }

  ngOnDestroy() {
    this.observer?.disconnect();
    this.observer = null;
  }
}
