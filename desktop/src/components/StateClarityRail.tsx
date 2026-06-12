type ClarityStepState = "done" | "active" | "waiting" | "blocked";

type ClarityStep = {
  label: string;
  state: ClarityStepState;
  detail?: string;
};

export default function StateClarityRail({
  label,
  state,
  steps
}: {
  label: string;
  state: string;
  steps: ClarityStep[];
}) {
  return (
    <div className="state-clarity-rail" data-clarity-state={state} aria-label={label}>
      {steps.slice(0, 5).map((step) => (
        <div className="state-clarity-step" data-step-state={step.state} key={`${step.label}-${step.state}`}>
          <span>{step.label}</span>
          {step.detail ? <small>{step.detail}</small> : null}
        </div>
      ))}
    </div>
  );
}
