import { Check, ChevronRight } from "lucide-react";
import { humanize } from "./primitives";
/** A visual map of a recorded state, never a trigger or a filing-readiness claim. */
export function StateMachine({
  states,
  current,
  label,
}: {
  states: string[];
  current?: string;
  label: string;
}) {
  const index = states.indexOf(current ?? "");
  return (
    <ol className="state-machine" aria-label={label}>
      {states.map((state, i) => (
        <li
          key={state}
          aria-current={current === state ? "step" : undefined}
          className={current === state ? "current" : index > i ? "past" : ""}
        >
          <span className="state-step">
            {index > i ? <Check size={12} /> : i + 1}
          </span>
          <span>{humanize(state)}</span>
          {i < states.length - 1 && <ChevronRight size={12} />}
        </li>
      ))}
    </ol>
  );
}
