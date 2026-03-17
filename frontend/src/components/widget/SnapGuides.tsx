/**
 * Snap guide lines rendered during widget drag near screen edges.
 * Uses RAF polling of refs to avoid re-renders from parent state changes.
 * 拖拽 Widget 接近屏幕边缘时渲染的吸附引导线。
 * 通过 RAF 轮询 ref 避免父组件 state 变化导致的重渲染。
 */

import { useEffect, useState } from 'react';
import type { RefObject } from 'react';
import { SNAP_THRESHOLD, WIDGET_WIDTH } from '../../utils/widgetUtils';
import type { WidgetId } from '../../types/widget';

interface InsertPreviewState {
  edge: 'left' | 'right';
  lineY: number;
  upperId: WidgetId | null;
  lowerId: WidgetId | null;
}

interface GuideOverlayState {
  nearLeft: boolean;
  nearRight: boolean;
  insertPreview: InsertPreviewState | null;
  upperHighlightTop: number | null;
  lowerHighlightTop: number | null;
}

interface SnapGuidesProps {
  isDragging: boolean;
  dragPositionRef: RefObject<{ x: number; y: number } | null>;
  insertPreviewRef: RefObject<InsertPreviewState | null>;
  containerRef: RefObject<HTMLDivElement | null>;
  containerWidth: number;
}

const HIGHLIGHT_HEIGHT = 12;

const EMPTY_OVERLAY_STATE: GuideOverlayState = {
  nearLeft: false,
  nearRight: false,
  insertPreview: null,
  upperHighlightTop: null,
  lowerHighlightTop: null,
};

function getWidgetBounds(
  container: HTMLDivElement,
  widgetId: WidgetId
): { top: number; height: number } | null {
  const selector = `[data-widget-id="${widgetId}"]`;
  const widgetEl = container.querySelector(selector) as HTMLElement | null;
  if (!widgetEl) return null;

  const containerRect = container.getBoundingClientRect();
  const widgetRect = widgetEl.getBoundingClientRect();
  return {
    top: widgetRect.top - containerRect.top,
    height: widgetRect.height,
  };
}

function isSamePreview(
  prev: InsertPreviewState | null,
  next: InsertPreviewState | null
): boolean {
  if (prev === next) return true;
  if (!prev || !next) return false;
  return (
    prev.edge === next.edge &&
    prev.lineY === next.lineY &&
    prev.upperId === next.upperId &&
    prev.lowerId === next.lowerId
  );
}

function isSameOverlayState(prev: GuideOverlayState, next: GuideOverlayState): boolean {
  return (
    prev.nearLeft === next.nearLeft &&
    prev.nearRight === next.nearRight &&
    prev.upperHighlightTop === next.upperHighlightTop &&
    prev.lowerHighlightTop === next.lowerHighlightTop &&
    isSamePreview(prev.insertPreview, next.insertPreview)
  );
}

export function SnapGuides({
  isDragging,
  dragPositionRef,
  insertPreviewRef,
  containerRef,
  containerWidth,
}: SnapGuidesProps) {
  const [overlayState, setOverlayState] = useState<GuideOverlayState>(EMPTY_OVERLAY_STATE);

  useEffect(() => {
    if (!isDragging) {
      setOverlayState((prev) => (isSameOverlayState(prev, EMPTY_OVERLAY_STATE) ? prev : EMPTY_OVERLAY_STATE));
      return;
    }

    let rafId = 0;
    const tick = () => {
      const pos = dragPositionRef.current;
      const container = containerRef.current;
      const effectiveWidth = containerWidth || container?.clientWidth || 0;
      const insertPreview = insertPreviewRef.current;

      if (!pos || !container || effectiveWidth <= 0) {
        setOverlayState((prev) => (isSameOverlayState(prev, EMPTY_OVERLAY_STATE) ? prev : EMPTY_OVERLAY_STATE));
        rafId = requestAnimationFrame(tick);
        return;
      }

      const nearLeft = pos.x < SNAP_THRESHOLD;
      const nearRight = effectiveWidth - (pos.x + WIDGET_WIDTH) < SNAP_THRESHOLD;
      const lowerBounds = insertPreview?.lowerId ? getWidgetBounds(container, insertPreview.lowerId) : null;
      const upperBounds = insertPreview?.upperId ? getWidgetBounds(container, insertPreview.upperId) : null;
      const nextState: GuideOverlayState = {
        nearLeft,
        nearRight,
        insertPreview: insertPreview ?? null,
        lowerHighlightTop: lowerBounds ? lowerBounds.top - 1 : null,
        upperHighlightTop: upperBounds
          ? upperBounds.top + upperBounds.height - HIGHLIGHT_HEIGHT + 1
          : null,
      };

      setOverlayState((prev) => (isSameOverlayState(prev, nextState) ? prev : nextState));
      rafId = requestAnimationFrame(tick);
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [isDragging, dragPositionRef, insertPreviewRef, containerRef, containerWidth]);

  const { nearLeft, nearRight, insertPreview, lowerHighlightTop, upperHighlightTop } = overlayState;
  if (!nearLeft && !nearRight && !insertPreview && lowerHighlightTop === null && upperHighlightTop === null) {
    return null;
  }

  const previewLineLeft = insertPreview?.edge === 'left'
    ? 0
    : Math.max(0, containerWidth - WIDGET_WIDTH);

  return (
    <div className="absolute inset-0 z-20 pointer-events-none">
      {nearLeft && (
        <div
          className="absolute left-0 top-0 bottom-0 w-0.5 bg-blue-400/60 shadow-[0_0_8px_rgba(59,130,246,0.5)]"
        />
      )}
      {nearRight && (
        <div
          className="absolute right-0 top-0 bottom-0 w-0.5 bg-blue-400/60 shadow-[0_0_8px_rgba(59,130,246,0.5)]"
        />
      )}
      {lowerHighlightTop !== null && insertPreview && (
        <div
          className="absolute"
          style={{
            top: Math.max(0, lowerHighlightTop),
            left: previewLineLeft,
            width: WIDGET_WIDTH,
            height: HIGHLIGHT_HEIGHT,
            background: 'linear-gradient(to bottom, rgba(96,165,250,0.3), transparent)',
          }}
        />
      )}
      {upperHighlightTop !== null && insertPreview && (
        <div
          className="absolute"
          style={{
            top: Math.max(0, upperHighlightTop),
            left: previewLineLeft,
            width: WIDGET_WIDTH,
            height: HIGHLIGHT_HEIGHT,
            background: 'linear-gradient(to top, rgba(96,165,250,0.3), transparent)',
          }}
        />
      )}
      {insertPreview && (
        <div
          className="absolute"
          style={{
            top: Math.max(0, insertPreview.lineY) - 4,
            left: previewLineLeft,
            width: WIDGET_WIDTH,
            height: 8,
            background: 'linear-gradient(to bottom, transparent, rgba(96,165,250,0.25), transparent)',
          }}
        />
      )}
    </div>
  );
}
