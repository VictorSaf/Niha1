interface FlowStep {
  label: string;
  detail?: string;
  color?: string;
}

interface Props {
  steps: FlowStep[];
  title?: string;
}

const DEFAULT_COLOR = 'var(--color-success)';

export function MiniFlow({ steps, title }: Props) {
  return (
    <div className="my-3">
      {title && <div className="text-[10px] uppercase tracking-wider text-navy-500 mb-2">{title}</div>}
      <div className="flex flex-col gap-0">
        {steps.map((step, i) => {
          const c = step.color ?? DEFAULT_COLOR;
          return (
            <div key={step.label} className="flex items-start gap-2">
              <div className="flex flex-col items-center flex-shrink-0 w-5">
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-semibold border"
                  style={{ borderColor: c, color: c, background: `${c}15` }}
                >
                  {i + 1}
                </div>
                {i < steps.length - 1 && <div className="w-px h-3 bg-navy-700" />}
              </div>
              <div className="pt-0.5 min-w-0 pb-1">
                <div className="text-[11px] text-navy-200 font-medium leading-tight">{step.label}</div>
                {step.detail && <div className="text-[10px] text-navy-500 leading-tight mt-0.5">{step.detail}</div>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
