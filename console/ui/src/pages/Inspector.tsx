import { useState } from 'react';
import { ModelsView } from './inspector/ModelsView';
import { RosbagsView } from './inspector/RosbagsView';

type Mode = 'models' | 'rosbags';

export function Inspector() {
  const [mode, setMode] = useState<Mode>('models');

  return (
    <div className="insp">
      <div className="insp-head">
        <h1 className="page-title">Inspector</h1>
        <div className="seg">
          <button className={mode === 'models' ? 'active' : ''} onClick={() => setMode('models')}>
            Models
          </button>
          <button className={mode === 'rosbags' ? 'active' : ''} onClick={() => setMode('rosbags')}>
            Rosbags
          </button>
        </div>
      </div>

      {mode === 'models' ? <ModelsView /> : <RosbagsView />}
    </div>
  );
}
