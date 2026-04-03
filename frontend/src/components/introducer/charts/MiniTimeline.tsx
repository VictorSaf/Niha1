interface TimelineEvent {
  year: string;
  label: string;
  detail?: string;
  color?: string;
  highlight?: boolean;
}

interface Props {
  events: TimelineEvent[];
  title?: string;
}

const DEFAULT_COLOR = 'var(--color-success)';

export function MiniTimeline({ events, title }: Props) {
  return (
    <div className="my-3">
      {title && <div className="text-[10px] uppercase tracking-wider text-navy-500 mb-2">{title}</div>}
      <div className="relative pl-4 border-l border-navy-700 space-y-2.5">
        {events.map((evt) => {
          const c = evt.color ?? DEFAULT_COLOR;
          return (
            <div key={evt.year + evt.label} className="relative">
              <div
                className="absolute -left-[calc(1rem+4.5px)] w-2.5 h-2.5 rounded-full border-2 top-0.5"
                style={{
                  borderColor: c,
                  background: evt.highlight ? c : 'var(--color-background)',
                }}
              />
              <div>
                <span className="text-[10px] font-mono font-semibold" style={{ color: c }}>{evt.year}</span>
                <span className="text-[11px] text-navy-200 ml-2 font-medium">{evt.label}</span>
                {evt.detail && <div className="text-[10px] text-navy-500 mt-0.5">{evt.detail}</div>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
