import { Fragment, type CSSProperties } from 'react';
import { CheckIcon, XIcon } from './icons';

export type StageState = 'done' | 'active' | 'pending' | 'failed' | 'skipped';

export interface Stage {
  key: string;
  label: string;
  state: StageState;
}

export function PipelineStages({ stages }: { stages: Stage[] }) {
  const visible = stages.filter((s) => s.state !== 'skipped');
  return (
    <div className="pipeline" role="list" aria-label="Verification pipeline">
      {visible.map((stage, i) => (
        <Fragment key={stage.key}>
          {i > 0 && (
            <div className={`pipeline-connector ${visible[i - 1].state === 'done' ? 'done' : ''}`} />
          )}
          <div className="pipeline-stage" role="listitem" style={{ '--rd': `${i * 45}ms` } as CSSProperties}>
            <div className={`pipeline-node ${stage.state}`} title={stage.label}>
              {stage.state === 'done' && <CheckIcon width={14} height={14} />}
              {stage.state === 'failed' && <XIcon width={14} height={14} />}
              {stage.state === 'active' && <span className="spinner spinner-dark" />}
              {stage.state === 'pending' && <span>{i + 1}</span>}
            </div>
            <span className="pipeline-label">{stage.label}</span>
          </div>
        </Fragment>
      ))}
    </div>
  );
}
